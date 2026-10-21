#!/usr/bin/env python3
"""Minimal EROFS metadata reader: walks an image and returns per-path
(mode, uid, gid, xattrs, symlink target). File contents are not decoded
(use fsck.erofs --extract for that); directories must be uncompressed."""
import struct, sys, json

XATTR_PREFIX = {1: 'user.', 2: 'system.posix_acl_access', 3: 'system.posix_acl_default',
                4: 'trusted.', 5: 'lustre.', 6: 'security.'}


class Erofs:
    def __init__(self, path):
        self.f = open(path, 'rb')
        sb = self.read(1024, 128)
        magic, = struct.unpack_from('<I', sb, 0)
        assert magic == 0xE0F5E1E2, 'not erofs'
        self.blkszbits = sb[12]
        self.bs = 1 << self.blkszbits
        self.root_nid, = struct.unpack_from('<H', sb, 14)
        self.meta_blkaddr, self.xattr_blkaddr = struct.unpack_from('<II', sb, 40)
        self.feature_incompat, = struct.unpack_from('<I', sb, 80)
        # long xattr name prefixes
        self.xattr_prefix_count = sb[91]
        self.xattr_prefix_start, = struct.unpack_from('<I', sb, 92)
        self.long_prefixes = []
        if self.xattr_prefix_count:
            off = self.xattr_prefix_start * 4
            for _ in range(self.xattr_prefix_count):
                ln, = struct.unpack('<H', self.read(off, 2))
                d = self.read(off + 2, ln)
                self.long_prefixes.append(XATTR_PREFIX.get(d[0], '') + d[1:].decode())
                off += (2 + ln + 3) & ~3

    def read(self, off, n):
        self.f.seek(off)
        return self.f.read(n)

    def inode(self, nid):
        off = self.meta_blkaddr * self.bs + nid * 32
        b = self.read(off, 64)
        fmt, = struct.unpack_from('<H', b, 0)
        ext = fmt & 1
        layout = (fmt >> 1) & 7
        icount, = struct.unpack_from('<H', b, 2)
        mode, = struct.unpack_from('<H', b, 4)
        if ext:
            size, = struct.unpack_from('<Q', b, 8)
            raw, = struct.unpack_from('<I', b, 16)
            uid, gid = struct.unpack_from('<II', b, 24)
            isize = 64
        else:
            size, = struct.unpack_from('<I', b, 8)
            raw, = struct.unpack_from('<I', b, 16)
            uid, gid = struct.unpack_from('<HH', b, 24)
            isize = 32
        xsize = 0 if icount == 0 else 12 + (icount - 1) * 4
        return dict(off=off, layout=layout, mode=mode, size=size, raw=raw, uid=uid, gid=gid,
                    isize=isize, xsize=xsize)

    def xattrs(self, ino):
        out = {}
        if not ino['xsize']:
            return out
        base = ino['off'] + ino['isize']
        hdr = self.read(base, ino['xsize'])
        shared_count = hdr[4]
        pos = 12
        entries = []
        for i in range(shared_count):
            sid, = struct.unpack_from('<I', hdr, pos)
            pos += 4
            entries.append(self.xattr_blkaddr * self.bs + sid * 4)
        # inline entries
        while pos + 4 <= len(hdr):
            nlen, nidx, vsz = struct.unpack_from('<BBH', hdr, pos)
            if nlen == 0 and nidx == 0 and vsz == 0:
                break
            entries.append(('inline', pos))
            pos += (4 + nlen + vsz + 3) & ~3
        for e in entries:
            if isinstance(e, tuple):
                p = e[1]
                nlen, nidx, vsz = struct.unpack_from('<BBH', hdr, p)
                name = hdr[p + 4:p + 4 + nlen]
                val = hdr[p + 4 + nlen:p + 4 + nlen + vsz]
            else:
                nlen, nidx, vsz = struct.unpack('<BBH', self.read(e, 4))
                name = self.read(e + 4, nlen)
                val = self.read(e + 4 + nlen, vsz)
            if nidx & 0x80:
                prefix = self.long_prefixes[nidx & 0x7f]
            else:
                prefix = XATTR_PREFIX.get(nidx, '?%d.' % nidx)
            out[prefix + name.decode('utf-8', 'replace')] = val
        return out

    def data(self, ino):
        """Return raw data for uncompressed (flat) inodes."""
        size, lay = ino['size'], ino['layout']
        if lay == 0:  # FLAT_PLAIN
            return self.read(ino['raw'] * self.bs, size)
        if lay == 2:  # FLAT_INLINE
            nblocks = size // self.bs
            head = self.read(ino['raw'] * self.bs, nblocks * self.bs) if nblocks else b''
            tail_off = ino['off'] + ino['isize'] + ino['xsize']
            return head + self.read(tail_off, size - nblocks * self.bs)
        raise ValueError('unsupported layout %d' % lay)

    def readdir(self, ino):
        d = self.data(ino)
        out = []
        for blk in range(0, len(d), self.bs):
            b = d[blk:blk + self.bs]
            first_nameoff, = struct.unpack_from('<H', b, 8)
            n = first_nameoff // 12
            ents = [struct.unpack_from('<QHBB', b, i * 12) for i in range(n)]
            for i, (nid, nameoff, ftype, _) in enumerate(ents):
                end = ents[i + 1][1] if i + 1 < n else len(b)
                name = b[nameoff:end].split(b'\0', 1)[0].decode('utf-8', 'surrogateescape')
                if name not in ('.', '..'):
                    out.append((name, nid))
        return out

    def walk(self):
        res = {}
        stack = [('', self.root_nid)]
        while stack:
            path, nid = stack.pop()
            ino = self.inode(nid)
            ent = dict(mode=ino['mode'], uid=ino['uid'], gid=ino['gid'],
                       xattrs={k: v.hex() for k, v in self.xattrs(ino).items()})
            typ = ino['mode'] & 0o170000
            if typ == 0o120000:
                try:
                    ent['link'] = self.data(ino).decode('utf-8', 'surrogateescape')
                except ValueError:
                    ent['link'] = None
            res[path or '.'] = ent
            if typ == 0o040000:
                for name, cnid in self.readdir(ino):
                    stack.append((path + '/' + name if path else name, cnid))
        return res


if __name__ == '__main__':
    meta = Erofs(sys.argv[1]).walk()
    json.dump(meta, open(sys.argv[2], 'w'))
    print(len(meta), 'entries')
