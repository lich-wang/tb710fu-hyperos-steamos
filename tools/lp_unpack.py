#!/usr/bin/env python3
"""lp_unpack.py SUPER_IMG OUT_DIR [NAME...] - extract logical partitions from an Android super image.

Reads the primary liblp metadata (slot 0) and writes every partition with at least one
extent (e.g. system_a, vendor_a ...) to OUT_DIR/<name>.img. Zero-length (_b) partitions are
skipped. Only linear extents are supported (all that super images contain).
"""
import os, struct, sys

GEOM_MAGIC, HDR_MAGIC, SECTOR = 0x616C4467, 0x414C5030, 512


def main():
    img, out = sys.argv[1], sys.argv[2]
    want = set(sys.argv[3:])
    f = open(img, "rb")
    f.seek(4096)
    magic, _, = struct.unpack("<II", f.read(8))
    assert magic == GEOM_MAGIC, "no liblp geometry at 4096"
    f.seek(4096 + 8 + 32)
    md_max, slots, lbs = struct.unpack("<III", f.read(12))
    f.seek(4096 * 3)                                   # reserved + geometry + backup geometry
    hdr = f.read(256)
    magic, major, minor, hsize = struct.unpack_from("<IHHI", hdr, 0)
    assert magic == HDR_MAGIC, "no liblp metadata header"
    tsize, = struct.unpack_from("<I", hdr, 44)
    pt_off, pt_n, pt_sz, ex_off, ex_n, ex_sz = struct.unpack_from("<6I", hdr, 80)
    f.seek(4096 * 3 + hsize)
    tables = f.read(tsize)
    extents = [struct.unpack_from("<QIQI", tables, ex_off + i * ex_sz) for i in range(ex_n)]
    os.makedirs(out, exist_ok=True)
    for i in range(pt_n):
        e = tables[pt_off + i * pt_sz: pt_off + (i + 1) * pt_sz]
        name = e[:36].rstrip(b"\0").decode()
        _, first, n_ext, _ = struct.unpack_from("<IIII", e, 36)
        if not n_ext or (want and name not in want):
            continue
        path = os.path.join(out, name + ".img")
        total = 0
        with open(path, "wb") as o:
            for num_sectors, ttype, tdata, _ in extents[first:first + n_ext]:
                assert ttype == 0, f"{name}: non-linear extent"
                f.seek(tdata * SECTOR)
                left = num_sectors * SECTOR
                while left:
                    b = f.read(min(left, 8 << 20))
                    o.write(b)
                    left -= len(b)
                total += num_sectors * SECTOR
        print(f"{name:16s} {total:>12d}  -> {path}")


if __name__ == "__main__":
    main()
