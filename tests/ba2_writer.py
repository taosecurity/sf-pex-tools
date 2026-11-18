# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Richard Bejtlich
"""A small BA2 writer for the tests only: makes the archive kinds Archive2 can't easily make on demand
(LZ4, stored, version 1, textures) and deliberately damaged ones. Not part of the tool and not a general packer:
name hashes are left at 0, which the reader never uses."""
import struct
import zlib


def gnrl(files, version=2, method="zlib", names=None, size_override=None):
    """files: [(stored name, bytes)]. method: zlib | lz4 | stored. size_override: {index: stated size}."""
    count = len(files)
    head = 24 + (8 if version in (2, 3) else 0) + (4 if version == 3 else 0)
    data_at = head + 36 * count
    blobs, records = [], []
    off = data_at
    for i, (_name, raw) in enumerate(files):
        if method == "stored":
            blob, packed = raw, 0
        elif method == "lz4":
            import lz4.block
            blob = lz4.block.compress(raw, store_size=False)
            packed = len(blob)
        else:
            blob = zlib.compress(raw)
            packed = len(blob)
        size = (size_override or {}).get(i, len(raw))
        records.append(struct.pack("<I4sIIQIII", 0, b"pex\0", 0, 0, off, packed, size, 0xBAADF00D))
        blobs.append(blob)
        off += len(blob)
    names_at = off
    out = struct.pack("<4sI4sIQ", b"BTDX", version, b"GNRL", count, names_at)
    if version in (2, 3):
        out += struct.pack("<II", 1, 0)
    if version == 3:
        out += struct.pack("<I", 3 if method == "lz4" else 0)
    out += b"".join(records) + b"".join(blobs)
    for name, _raw in (names or files):
        n = name.encode("utf-8")
        out += struct.pack("<H", len(n)) + n
    return out


def dx10(name, width, height, fmt, mip_data, version=2):
    """One texture, one chunk per mip level given in mip_data (zlib-packed)."""
    head = 24 + (8 if version in (2, 3) else 0) + (4 if version == 3 else 0)
    record_len = 24 + 24 * len(mip_data)
    off = head + record_len
    chunks, blobs = [], []
    for level, raw in enumerate(mip_data):
        blob = zlib.compress(raw)
        chunks.append(struct.pack("<QIIHHI", off, len(blob), len(raw), level, level, 0xBAADF00D))
        blobs.append(blob)
        off += len(blob)
    rec = struct.pack("<I4sIBBHHHBBBB", 0, b"dds\0", 0, 0, len(mip_data), 24, height, width, len(mip_data), fmt, 0, 8)
    out = struct.pack("<4sI4sIQ", b"BTDX", version, b"DX10", 1, off)
    if version in (2, 3):
        out += struct.pack("<II", 1, 0)
    if version == 3:
        out += struct.pack("<I", 0)
    n = name.encode("utf-8")
    return out + rec + b"".join(chunks) + b"".join(blobs) + struct.pack("<H", len(n)) + n
