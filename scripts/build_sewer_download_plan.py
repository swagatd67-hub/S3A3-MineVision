from __future__ import annotations

import csv
import json
import struct
from pathlib import Path


TAIL = Path("approved-data/sewer-ml/images/train00.tail")
SUBSET_CSV = Path("approved-data/sewer-ml/train00_subset.csv")
OUTPUT = Path("approved-data/sewer-ml/train00_download_plan.json")

ARCHIVE_SIZE = 19_736_428_102


def read_subset() -> set[str]:
    with SUBSET_CSV.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return {
            row["Filename"]
            for row in csv.DictReader(handle)
        }


def parse_zip64_extra(
    extra: bytes,
    *,
    need_uncompressed: bool,
    need_compressed: bool,
    need_offset: bool,
) -> tuple[int | None, int | None, int | None]:
    pos = 0
    uncompressed = None
    compressed = None
    offset = None

    while pos + 4 <= len(extra):
        field_id, field_size = struct.unpack_from("<HH", extra, pos)
        field_start = pos + 4
        field_end = field_start + field_size

        if field_end > len(extra):
            break

        if field_id == 0x0001:
            cursor = field_start

            if need_uncompressed:
                if cursor + 8 > field_end:
                    raise RuntimeError("Malformed ZIP64 extra field")
                uncompressed = struct.unpack_from(
                    "<Q", extra, cursor
                )[0]
                cursor += 8

            if need_compressed:
                if cursor + 8 > field_end:
                    raise RuntimeError("Malformed ZIP64 extra field")
                compressed = struct.unpack_from(
                    "<Q", extra, cursor
                )[0]
                cursor += 8

            if need_offset:
                if cursor + 8 > field_end:
                    raise RuntimeError("Malformed ZIP64 extra field")
                offset = struct.unpack_from(
                    "<Q", extra, cursor
                )[0]

            break

        pos = field_end

    return uncompressed, compressed, offset


def main() -> None:
    selected = read_subset()
    print(f"Selected filenames: {len(selected)}")

    data = TAIL.read_bytes()
    tail_start = ARCHIVE_SIZE - len(data)

    eocd64 = data.rfind(b"PK\x06\x06")
    if eocd64 < 0:
        raise RuntimeError("ZIP64 EOCD not found")

    entry_count = struct.unpack_from(
        "<Q", data, eocd64 + 32
    )[0]

    central_size = struct.unpack_from(
        "<Q", data, eocd64 + 40
    )[0]

    central_offset = struct.unpack_from(
        "<Q", data, eocd64 + 48
    )[0]

    local_start = central_offset - tail_start
    local_end = local_start + central_size

    if local_start < 0 or local_end > len(data):
        raise RuntimeError(
            "Central directory is not fully contained in train00.tail"
        )

    pos = local_start
    entries: dict[str, dict] = {}

    for _ in range(entry_count):
        if data[pos:pos + 4] != b"PK\x01\x02":
            raise RuntimeError(
                f"Invalid central directory signature at offset {pos}"
            )

        # Central-directory fixed header fields are 4 bytes here.
        compressed_size_32 = struct.unpack_from(
            "<I", data, pos + 20
        )[0]

        uncompressed_size_32 = struct.unpack_from(
            "<I", data, pos + 24
        )[0]

        filename_length = struct.unpack_from(
            "<H", data, pos + 28
        )[0]

        extra_length = struct.unpack_from(
            "<H", data, pos + 30
        )[0]

        comment_length = struct.unpack_from(
            "<H", data, pos + 32
        )[0]

        local_offset_32 = struct.unpack_from(
            "<I", data, pos + 42
        )[0]

        name_start = pos + 46
        name_end = name_start + filename_length

        extra_start = name_end
        extra_end = extra_start + extra_length

        name = data[
            name_start:name_end
        ].decode("utf-8", errors="replace")

        extra = data[extra_start:extra_end]

        need_uncompressed = uncompressed_size_32 == 0xFFFFFFFF
        need_compressed = compressed_size_32 == 0xFFFFFFFF
        need_offset = local_offset_32 == 0xFFFFFFFF

        zip64_uncompressed, zip64_compressed, zip64_offset = (
            parse_zip64_extra(
                extra,
                need_uncompressed=need_uncompressed,
                need_compressed=need_compressed,
                need_offset=need_offset,
            )
        )

        uncompressed_size = (
            zip64_uncompressed
            if need_uncompressed
            else uncompressed_size_32
        )

        compressed_size = (
            zip64_compressed
            if need_compressed
            else compressed_size_32
        )

        local_header_offset = (
            zip64_offset
            if need_offset
            else local_offset_32
        )

        if compressed_size is None or local_header_offset is None:
            raise RuntimeError(
                f"Missing ZIP64 metadata for {name}"
            )

        entries[name] = {
            "filename": name,
            "compressed_size": compressed_size,
            "uncompressed_size": uncompressed_size,
            "local_header_offset": local_header_offset,
        }

        pos = extra_end + comment_length

    missing = sorted(selected - entries.keys())

    if missing:
        raise RuntimeError(
            f"{len(missing)} selected filenames were not found "
            f"in train00.zip. First: {missing[:10]}"
        )

    plan = [
        entries[name]
        for name in sorted(selected)
    ]

    compressed_total = sum(
        item["compressed_size"]
        for item in plan
    )

    uncompressed_total = sum(
        item["uncompressed_size"]
        for item in plan
    )

    if compressed_total > ARCHIVE_SIZE:
        raise RuntimeError(
            "Computed compressed payload exceeds archive size; "
            "ZIP parsing is still incorrect."
        )

    payload = {
        "archive": "train00.zip",
        "archive_size": ARCHIVE_SIZE,
        "selected_files": len(plan),
        "compressed_payload_bytes": compressed_total,
        "compressed_payload_mib": round(
            compressed_total / (1024 ** 2), 2
        ),
        "uncompressed_payload_bytes": uncompressed_total,
        "uncompressed_payload_mib": round(
            uncompressed_total / (1024 ** 2), 2
        ),
        "entries": plan,
    }

    OUTPUT.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )

    print(f"Matched entries: {len(plan)}")
    print(
        "Compressed payload:",
        round(compressed_total / (1024 ** 2), 2),
        "MiB",
    )
    print(
        "Uncompressed payload:",
        round(uncompressed_total / (1024 ** 2), 2),
        "MiB",
    )
    print(f"Plan: {OUTPUT}")


if __name__ == "__main__":
    main()