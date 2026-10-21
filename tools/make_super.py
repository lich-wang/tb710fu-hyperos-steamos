#!/usr/bin/env python3
"""Build a raw super image (liblp metadata v10.2, virtual A/B flag) from partition images.

usage: make_super.py OUT.img DEVICE_SIZE name=img [name=img ...]
Every name gets an _a partition with the image and an empty _b partition, in groups
qti_dynamic_partitions_a / _b. Only the used region is written (geometry + metadata +
partition data); the rest of the physical super partition is left untouched on flash.
"""
import hashlib, os, struct, sys

SECTOR = 512
ALIGN = 1 << 20
MD_MAX = 65536
SLOTS = 3
LBS = 4096
LINUX_ROOT_OFFSET = 10 << 30
GEOM_MAGIC = 0x616C4467
HDR_MAGIC = 0x414C5030


def pad(b, n):
    return b + b'\0' * (n - len(b))


def build(out, dev_size, parts):
    first_sector = 2048                       # 1 MiB: reserved + 2 geometry + 2*3 metadata slots fit below
    assert (4096 + 2 * 4096 + 2 * SLOTS * MD_MAX) <= first_sector * SECTOR
    names = sorted(parts)
    group_max = (dev_size - first_sector * SECTOR) // ALIGN * ALIGN
    # layout
    cur = first_sector * SECTOR
    layout = []
    for n in names:
        size = os.path.getsize(parts[n])
        size_al = (size + LBS - 1) // LBS * LBS
        layout.append((n, cur, size, size_al))
        cur = (cur + size_al + ALIGN - 1) // ALIGN * ALIGN
    used_end = cur
    assert used_end <= dev_size, 'does not fit'
    # TB710FU: [10 GiB, end) of the physical super holds the Debian/Linux root fs
    # (ext4 label tb710fu-root, mounted by the kShimC Linux initramfs via loop offset).
    if used_end > LINUX_ROOT_OFFSET and not os.environ.get('TB_ALLOW_LINUX_OVERLAP'):
        sys.exit(f'super content ends at {used_end/2**30:.3f} GiB, past the Linux root at '
                 f'{LINUX_ROOT_OFFSET/2**30:.0f} GiB (set TB_ALLOW_LINUX_OVERLAP=1 to override)')
    total_a = sum(x[3] for x in layout)
    assert total_a <= group_max

    # tables
    pt, ex = b'', b''
    ext_i = 0
    for n, off, size, size_al in layout:
        pt += pad(f'{n}_a'.encode(), 36) + struct.pack('<IIII', 0, ext_i, 1, 1)
        ex += struct.pack('<QIQI', size_al // SECTOR, 0, off // SECTOR, 0)
        ext_i += 1
        pt += pad(f'{n}_b'.encode(), 36) + struct.pack('<IIII', 0, ext_i, 0, 2)
    gr = pad(b'default', 36) + struct.pack('<IQ', 0, 0)
    gr += pad(b'qti_dynamic_partitions_a', 36) + struct.pack('<IQ', 0, group_max)
    gr += pad(b'qti_dynamic_partitions_b', 36) + struct.pack('<IQ', 0, group_max)
    bd = struct.pack('<QIIQ', first_sector, ALIGN, 0, dev_size) + pad(b'super', 36) + struct.pack('<I', 0)
    npart, next_ = len(names) * 2, len(names)
    tables = pt + ex + gr + bd
    desc = struct.pack('<12I',
                       0, npart, 52,
                       len(pt), next_, 24,
                       len(pt) + len(ex), 3, 48,
                       len(pt) + len(ex) + len(gr), 1, 64)
    hdr_size = 256
    def header():
        h = struct.pack('<IHHI', HDR_MAGIC, 10, 2, hdr_size) + b'\0' * 32
        h += struct.pack('<I', len(tables)) + hashlib.sha256(tables).digest()
        h += desc + struct.pack('<I', 1)            # flags: LP_HEADER_FLAG_VIRTUAL_AB_DEVICE
        h = pad(h, hdr_size)
        ck = hashlib.sha256(h).digest()
        return h[:12] + ck + h[44:]
    md = pad(header() + tables, MD_MAX)
    g = struct.pack('<II', GEOM_MAGIC, 52) + b'\0' * 32 + struct.pack('<III', MD_MAX, SLOTS, LBS)
    g = g[:8] + hashlib.sha256(g).digest() + g[40:]
    g = pad(g, 4096)

    with open(out, 'wb') as f:
        f.write(b'\0' * 4096 + g + g)
        for _ in range(2 * SLOTS):
            f.write(md)
        for n, off, size, size_al in layout:
            f.seek(off)
            with open(parts[n], 'rb') as src:
                while True:
                    b = src.read(64 << 20)
                    if not b:
                        break
                    f.write(b)
        f.truncate(used_end)
    for n, off, size, size_al in layout:
        print(f'  {n+"_a":16} start {off/1e6:9.1f} MB  size {size/1e6:9.1f} MB')
    print(f'super: device {dev_size/1e9:.3f} GB, group max {group_max/1e9:.3f} GB, written {used_end/1e9:.3f} GB')


if __name__ == '__main__':
    out, dev = sys.argv[1], int(sys.argv[2], 0)
    parts = dict(a.split('=', 1) for a in sys.argv[3:])
    build(out, dev, parts)
