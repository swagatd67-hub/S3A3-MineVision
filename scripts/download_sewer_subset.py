from __future__ import annotations

import argparse
import json
import struct
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from base64 import b64encode


DEFAULT_URL = (
    "https://sciencedata.dk/public/"
    "Large%20AAU%20files/Sewer_ML/train00.zip"
)


def load_plan(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def auth_header(username: str, password: str) -> str:
    token = b64encode(
        f"{username}:{password}".encode("utf-8")
    ).decode("ascii")
    return f"Basic {token}"


def fetch_range(
    url: str,
    start: int,
    end: int,
    auth: str,
    *,
    retries: int = 4,
    timeout: int = 120,
) -> bytes:
    for attempt in range(1, retries + 1):
        request = Request(url)
        request.add_header("Authorization", auth)
        request.add_header("Range", f"bytes={start}-{end}")
        request.add_header("Accept", "*/*")

        try:
            with urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                body = response.read()

                expected = end - start + 1

                if status != 206:
                    raise RuntimeError(
                        f"Expected HTTP 206, got {status}"
                    )

                if len(body) != expected:
                    raise RuntimeError(
                        f"Range length mismatch: expected {expected}, "
                        f"got {len(body)}"
                    )

                content_range = response.headers.get("Content-Range", "")
                expected_prefix = f"bytes {start}-{end}/"

                if not content_range.startswith(expected_prefix):
                    raise RuntimeError(
                        f"Unexpected Content-Range: {content_range}"
                    )

                return body

        except Exception as exc:
            if attempt == retries:
                raise

            delay = 2 ** (attempt - 1)
            print(
                f"  retry {attempt}/{retries - 1}: {exc}; "
                f"sleeping {delay}s"
            )
            time.sleep(delay)

    raise RuntimeError("unreachable")


def local_member_start(
    plan_entry: dict[str, Any],
    local_header: bytes,
) -> int:
    if local_header[:4] != b"PK\x03\x04":
        raise RuntimeError(
            f"Invalid local header for {plan_entry['filename']}"
        )

    name_length = struct.unpack_from("<H", local_header, 26)[0]
    extra_length = struct.unpack_from("<H", local_header, 28)[0]

    return 30 + name_length + extra_length


def extract_member_bytes(
    url: str,
    entry: dict[str, Any],
    auth: str,
) -> bytes:
    offset = int(entry["local_header_offset"])
    compressed_size = int(entry["compressed_size"])

    # A generous but still small header read. The local header + ZIP64 extra
    # metadata is tiny compared with the image payload.
    header = fetch_range(
        url,
        offset,
        offset + 4095,
        auth,
    )

    data_start_delta = local_member_start(
        entry,
        header,
    )

    data_start = offset + data_start_delta
    data_end = data_start + compressed_size - 1

    compressed = fetch_range(
        url,
        data_start,
        data_end,
        auth,
    )

    method = int(entry.get("compression_method", 0))

    if method == 0:
        return compressed

    if method != 8:
        raise RuntimeError(
            f"Unsupported ZIP compression method {method} "
            f"for {entry['filename']}"
        )

    import zlib

    try:
        return zlib.decompress(
            compressed,
            wbits=-15,
        )
    except zlib.error as exc:
        raise RuntimeError(
            f"Raw-deflate decompression failed for {entry['filename']}"
        ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download selected Sewer-ML train00 PNGs using HTTP ranges."
    )
    parser.add_argument(
        "--plan",
        default="approved-data/sewer-ml/train00_download_plan.json",
    )
    parser.add_argument(
        "--output",
        default="approved-data/sewer-ml/images/train00_subset",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_URL,
    )
    parser.add_argument(
        "--username",
        required=True,
    )
    parser.add_argument(
        "--password",
        required=True,
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=0,
        help="0 means all remaining images",
    )
    parser.add_argument(
        "--pause-ms",
        type=int,
        default=0,
    )
    args = parser.parse_args()

    plan_path = Path(args.plan)
    output_root = Path(args.output)
    state_path = output_root / ".download_state.json"

    plan = load_plan(plan_path)
    entries = plan["entries"]

    output_root.mkdir(parents=True, exist_ok=True)

    completed: set[str] = set()

    if state_path.exists():
        state = json.loads(
            state_path.read_text(encoding="utf-8")
        )
        completed = set(state.get("completed", []))

    auth = auth_header(
        args.username,
        args.password,
    )

    selected = entries[args.start_index:]
    if args.max_images > 0:
        selected = selected[:args.max_images]

    print(f"Plan entries: {len(entries)}")
    print(f"Already completed: {len(completed)}")
    print(f"This run will consider: {len(selected)}")

    for index, entry in enumerate(selected, start=args.start_index):
        filename = str(entry["filename"])
        target = output_root / filename

        if filename in completed and target.exists():
            continue

        print(
            f"[{index + 1}/{len(entries)}] "
            f"{filename} "
            f"{entry['compressed_size']} bytes compressed"
        )

        try:
            raw = extract_member_bytes(
                args.base_url,
                entry,
                auth,
            )

            expected_size = int(entry["uncompressed_size"])
            if len(raw) != expected_size:
                raise RuntimeError(
                    f"uncompressed size mismatch: expected {expected_size}, "
                    f"got {len(raw)}"
                )

            temp = target.with_suffix(
                target.suffix + ".part"
            )
            temp.write_bytes(raw)
            temp.replace(target)

            completed.add(filename)
            state_path.write_text(
                json.dumps(
                    {
                        "completed": sorted(completed),
                        "last_filename": filename,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        except Exception as exc:
            print(f"ERROR {filename}: {exc}")
            print(
                "Stopping so the failed entry can be inspected; "
                "completed files remain recorded."
            )
            raise

        if args.pause_ms > 0:
            time.sleep(args.pause_ms / 1000.0)

    print(
        f"Completed: {len(completed)}/{len(entries)} "
        f"planned files"
    )


if __name__ == "__main__":
    main()
