from __future__ import annotations

import argparse
import json
import struct
import subprocess
import time
import zlib
from pathlib import Path


BASE_URL = (
    "https://sciencedata.dk/public/"
    "Large%20AAU%20files/Sewer_ML/train00.zip"
)


def load_plan(path: Path) -> dict:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def fetch_range(
    *,
    url: str,
    username: str,
    password: str,
    start: int,
    end: int,
    output: Path,
) -> None:
    if start > end:
        raise ValueError("start must be <= end")

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "curl.exe",
        "--fail",
        "--silent",
        "--show-error",
        "--location-trusted",
        "--retry",
        "5",
        "--retry-delay",
        "2",
        "--retry-all-errors",
        "--connect-timeout",
        "30",
        "--max-time",
        "300",
        "-u",
        f"{username}:{password}",
        "-r",
        f"{start}-{end}",
        "-o",
        str(output),
        url,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"curl failed ({result.returncode}): "
            f"{result.stderr.strip()}"
        )

    expected = end - start + 1
    actual = output.stat().st_size

    if actual != expected:
        raise RuntimeError(
            f"range size mismatch: "
            f"expected {expected}, got {actual}"
        )


def parse_local_header(
    header: bytes,
) -> int:
    if header[:4] != b"PK\x03\x04":
        raise RuntimeError(
            "invalid ZIP local header"
        )

    name_length = struct.unpack_from(
        "<H",
        header,
        26,
    )[0]

    extra_length = struct.unpack_from(
        "<H",
        header,
        28,
    )[0]

    return 30 + name_length + extra_length


def download_one(
    *,
    entry: dict,
    username: str,
    password: str,
    output_root: Path,
    scratch_root: Path,
) -> bool:
    filename = str(
        entry["filename"]
    )

    target = output_root / filename

    expected_size = int(
        entry["uncompressed_size"]
    )

    # Already downloaded and valid.
    if target.exists():
        if target.stat().st_size == expected_size:
            return False

        # Remove incomplete/corrupt file.
        target.unlink()

    local_offset = int(
        entry["local_header_offset"]
    )

    compressed_size = int(
        entry["compressed_size"]
    )

    header_file = (
        scratch_root / f"{filename}.header"
    )

    compressed_file = (
        scratch_root / f"{filename}.compressed"
    )

    part_file = target.with_suffix(
        ".png.part"
    )

    # Download local ZIP header.
    fetch_range(
        url=BASE_URL,
        username=username,
        password=password,
        start=local_offset,
        end=local_offset + 4095,
        output=header_file,
    )

    header = header_file.read_bytes()

    payload_offset = (
        local_offset
        + parse_local_header(header)
    )

    compressed_start = payload_offset
    compressed_end = (
        payload_offset
        + compressed_size
        - 1
    )

    # Download compressed member.
    fetch_range(
        url=BASE_URL,
        username=username,
        password=password,
        start=compressed_start,
        end=compressed_end,
        output=compressed_file,
    )

    compressed = (
        compressed_file.read_bytes()
    )

    if len(compressed) != compressed_size:
        raise RuntimeError(
            f"{filename}: compressed size mismatch"
        )

    # Sewer-ML train00 PNG entries use raw DEFLATE.
    raw = zlib.decompress(
        compressed,
        wbits=-15,
    )

    if len(raw) != expected_size:
        raise RuntimeError(
            f"{filename}: expected "
            f"{expected_size} bytes after "
            f"decompression, got {len(raw)}"
        )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    part_file.write_bytes(raw)
    part_file.replace(target)

    header_file.unlink(
        missing_ok=True
    )

    compressed_file.unlink(
        missing_ok=True
    )

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Resumable selective downloader "
            "for the Sewer-ML train00 archive."
        )
    )

    parser.add_argument(
        "--plan",
        default=(
            "approved-data/sewer-ml/"
            "train00_download_plan.json"
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "approved-data/sewer-ml/"
            "images/train00_subset"
        ),
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
        "--max-images",
        type=int,
        default=0,
        help=(
            "Maximum number of missing images "
            "to download in this run. "
            "0 = all remaining images."
        ),
    )

    parser.add_argument(
        "--pause-ms",
        type=int,
        default=1500,
        help=(
            "Pause after each successfully "
            "downloaded image."
        ),
    )

    args = parser.parse_args()

    plan = load_plan(
        Path(args.plan)
    )

    entries = plan["entries"]

    output_root = Path(
        args.output
    )

    scratch_root = (
        output_root / ".scratch"
    )

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    scratch_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Find the first missing or invalid file.
    first_missing = None

    for index, entry in enumerate(entries):
        filename = str(
            entry["filename"]
        )

        target = (
            output_root / filename
        )

        expected_size = int(
            entry["uncompressed_size"]
        )

        if not target.exists():
            first_missing = index
            break

        if target.stat().st_size != expected_size:
            first_missing = index
            break

    if first_missing is None:
        print(
            "All planned images are "
            "already downloaded."
        )
        return

    remaining = entries[
        first_missing:
    ]

    if args.max_images > 0:
        remaining = remaining[
            :args.max_images
        ]

    print(
        f"Total plan entries: "
        f"{len(entries)}"
    )

    print(
        f"First missing index: "
        f"{first_missing}"
    )

    print(
        f"First missing file: "
        f"{entries[first_missing]['filename']}"
    )

    print(
        f"This run: "
        f"{len(remaining)} images"
    )

    completed = 0

    for offset, entry in enumerate(
        remaining,
        start=first_missing,
    ):
        filename = str(
            entry["filename"]
        )

        progress_number = (
            offset + 1
        )

        print(
            f"[{progress_number}/"
            f"{len(entries)}] "
            f"{filename}"
        )

        try:
            downloaded = download_one(
                entry=entry,
                username=args.username,
                password=args.password,
                output_root=output_root,
                scratch_root=scratch_root,
            )

            if downloaded:
                completed += 1

                if args.pause_ms > 0:
                    time.sleep(
                        args.pause_ms / 1000.0
                    )

        except Exception as exc:
            print(
                f"ERROR: {filename}: {exc}"
            )

            print(
                "Stopping. Previously "
                "completed files are preserved."
            )

            raise

    print(
        f"Completed this run: "
        f"{completed}/{len(remaining)} new images."
    )


if __name__ == "__main__":
    main()