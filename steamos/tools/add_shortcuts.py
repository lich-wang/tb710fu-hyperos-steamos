#!/usr/bin/env python3
"""Append non-Steam shortcuts to Steam's binary shortcuts.vdf (Steam must be stopped).
usage: add_shortcuts.py shortcuts.vdf"""
import struct, sys, zlib

def parse(b, i):
    d = {}
    while True:
        t = b[i]; i += 1
        if t == 8:
            return d, i
        j = b.index(0, i); k = b[i:j].decode(); i = j + 1
        if t == 0:
            d[k], i = parse(b, i)
        elif t == 1:
            j = b.index(0, i); d[k] = b[i:j].decode(); i = j + 1
        elif t == 2:
            d[k] = struct.unpack_from('<i', b, i)[0]; i += 4
        else:
            raise ValueError(t)

def dump(d):
    o = b''
    for k, v in d.items():
        if isinstance(v, dict):
            o += b'\x00' + k.encode() + b'\x00' + dump(v)
        elif isinstance(v, str):
            o += b'\x01' + k.encode() + b'\x00' + v.encode() + b'\x00'
        else:
            o += b'\x02' + k.encode() + b'\x00' + struct.pack('<i', v)
    return o + b'\x08'

def entry(name, exe, opts):
    appid = (zlib.crc32((exe + name).encode()) | 0x80000000)
    appid = struct.unpack('<i', struct.pack('<I', appid))[0]
    return {'appid': appid, 'AppName': name, 'Exe': exe, 'StartDir': '/usr/local/bin/', 'icon': '',
            'ShortcutPath': '', 'LaunchOptions': opts, 'IsHidden': 0, 'AllowDesktopConfig': 1,
            'AllowOverlay': 1, 'OpenVR': 0, 'Devkit': 0, 'DevkitGameID': '', 'DevkitOverrideAppID': 0,
            'LastPlayTime': 0, 'FlatpakAppID': '', 'sortas': '', 'tags': {}}

p = sys.argv[1]
b = open(p, 'rb').read()
root, _ = parse(b, b.index(0, 1) + 1) if b[:1] == b"\x00" else ({}, 0)
sc = root
new = [entry('触摸：点击模式', '"/usr/local/bin/tb-touch-mode"', '1'),
       entry('触摸：原生模式', '"/usr/local/bin/tb-touch-mode"', '4')]
names = {v.get('AppName') for v in sc.values()}
n = len(sc)
for e in new:
    if e['AppName'] not in names:
        sc[str(n)] = e; n += 1
open(p, 'wb').write(b'\x00shortcuts\x00' + dump(sc) + b'\x08')
print('shortcuts:', [v['AppName'] for v in sc.values()])
