from pathlib import Path
import struct


TAIL = Path("approved-data/sewer-ml/images/train00.tail")
ARCHIVE_SIZE = 19_736_428_102
OUTPUT = Path("approved-data/sewer-ml/images/train00-files.txt")

data = TAIL.read_bytes()

tail_start = ARCHIVE_SIZE - len(data)

eocd64 = data.rfind(b"PK\x06\x06")
if eocd64 < 0:
    raise RuntimeError("ZIP64 EOCD not found")

entry_count = struct.unpack_from("<Q", data, eocd64 + 32)[0]
central_size = struct.unpack_from("<Q", data, eocd64 + 40)[0]
central_offset = struct.unpack_from("<Q", data, eocd64 + 48)[0]

local_start = central_offset - tail_start
local_end = local_start + central_size

if local_start < 0 or local_end > len(data):
    raise RuntimeError(
        f"Central directory is not fully contained in tail: "
        f"{local_start}:{local_end} / {len(data)}"
    )

pos = local_start
names: list[str] = []

for index in range(entry_count):
    if data[pos:pos + 4] != b"PK\x01\x02":
        raise RuntimeError(
            f"Central-directory signature missing at entry {index}, offset {pos}"
        )

    # Central directory fixed header is 46 bytes.
    filename_length = struct.unpack_from("<H", data, pos + 28)[0]
    extra_length = struct.unpack_from("<H", data, pos + 30)[0]
    comment_length = struct.unpack_from("<H", data, pos + 32)[0]

    name_start = pos + 46
    name_end = name_start + filename_length

    name = data[name_start:name_end].decode("utf-8", errors="replace")
    names.append(name)

    pos = name_end + extra_length + comment_length

if pos > local_end:
    raise RuntimeError("Parsed past central-directory boundary")

OUTPUT.write_text("\n".join(names) + "\n", encoding="utf-8")

print(f"Entries parsed: {len(names)}")
print(f"Output: {OUTPUT}")
print(f"First 20:")
for name in names[:20]:
    print(name)

print("\nLast 20:")
for name in names[-20:]:
    print(name)