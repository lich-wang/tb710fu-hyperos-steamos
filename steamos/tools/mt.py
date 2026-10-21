#!/usr/bin/env python3
"""mt.py CMD...  - scripted multi-touch gestures on a uinput touchscreen "tb mt test"
coords in panel pixels (3200x2000).  Commands (run in order):
  wait S | tap X,Y | hold X,Y,S | drag X1,Y1,X2,Y2,S | pan2 X,Y,DX,DY,S | pinch X,Y,D1,D2,S"""
import fcntl, os, struct, sys, time
EV = struct.Struct("qqHHi")
u = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
for t in (1, 3): fcntl.ioctl(u, 0x40045564, t)
fcntl.ioctl(u, 0x40045565, 0x14a); fcntl.ioctl(u, 0x4004556e, 1)
for code, mx in ((0, 32000), (1, 20000), (0x35, 32000), (0x36, 20000), (0x2f, 9), (0x39, 65535)):
    fcntl.ioctl(u, 0x40045567, code); fcntl.ioctl(u, 0x401c5504, struct.pack("HH6i", code, 0, 0, 0, mx, 0, 0, 0))
fcntl.ioctl(u, 0x405c5503, struct.pack("HHHH80sI", 6, 0x1234, 0x5680, 1, b"tb mt test", 0))
fcntl.ioctl(u, 0x5501); time.sleep(3)
tid = [100]
def frame(pts):  # pts: {slot: (x,y) or None}
    ev = []
    for s, p in pts.items():
        ev.append((3, 0x2f, s))
        if p is None: ev.append((3, 0x39, -1))
        else:
            if p[2]: tid[0] += 1; ev.append((3, 0x39, tid[0]))
            ev += [(3, 0x35, int(p[0] * 10)), (3, 0x36, int(p[1] * 10))]
    down = any(p is not None for p in pts.values())
    ev.append((1, 0x14a, 1 if down else 0))
    os.write(u, b"".join(EV.pack(0, 0, *e) for e in ev) + EV.pack(0, 0, 0, 0, 0))
def path(starts, ends, dur):
    n = max(2, int(dur / 0.016))
    frame({i: (s[0], s[1], True) for i, s in enumerate(starts)})
    for k in range(1, n + 1):
        time.sleep(dur / n); f = k / n
        frame({i: (s[0] + (e[0] - s[0]) * f, s[1] + (e[1] - s[1]) * f, False) for i, (s, e) in enumerate(zip(starts, ends))})
    time.sleep(0.03); frame({i: None for i in range(len(starts))}); frame({}) if False else None
for cmd in sys.argv[1:]:
    op, _, a = cmd.partition(" "); v = [float(x) for x in a.replace(",", " ").split()]
    if op == "wait": time.sleep(v[0])
    elif op == "tap": path([(v[0], v[1])], [(v[0], v[1])], 0.06)
    elif op == "hold": path([(v[0], v[1])], [(v[0], v[1])], v[2])
    elif op == "drag": path([(v[0], v[1])], [(v[2], v[3])], v[4])
    elif op == "tap2": path([(v[0] - 150, v[1]), (v[0] + 150, v[1])], [(v[0] - 150, v[1]), (v[0] + 150, v[1])], 0.08)
    elif op == "pan2": x, y, dx, dy, d = v; path([(x - 150, y), (x + 150, y)], [(x - 150 + dx, y + dy), (x + 150 + dx, y + dy)], d)
    elif op == "pinch": x, y, d1, d2, d = v; path([(x - d1 / 2, y), (x + d1 / 2, y)], [(x - d2 / 2, y), (x + d2 / 2, y)], d)
    time.sleep(0.3)
time.sleep(0.5)
