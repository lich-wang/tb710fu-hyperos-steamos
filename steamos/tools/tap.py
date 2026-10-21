# tap.py x,y [x,y ...]  - synthetic touchscreen taps (coords in 0..32000 x 0..20000) via uinput
import fcntl, os, struct, sys, time
EV = struct.Struct("qqHHi")
u = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
for code in (1, 3): fcntl.ioctl(u, 0x40045564, code)
fcntl.ioctl(u, 0x40045565, 0x14a)
fcntl.ioctl(u, 0x4004556e, 1)
for code, mx in ((0, 32000), (1, 20000), (0x35, 32000), (0x36, 20000), (0x2f, 0), (0x39, 65535)):
    fcntl.ioctl(u, 0x40045567, code)
    fcntl.ioctl(u, 0x401c5504, struct.pack("HH6i", code, 0, 0, 0, mx, 0, 0, 0))
fcntl.ioctl(u, 0x405c5503, struct.pack("HHHH80sI", 6, 0x1234, 0x5678, 1, b"tb test taps", 0))
fcntl.ioctl(u, 0x5501)
time.sleep(2)
def emit(evs): os.write(u, b"".join(EV.pack(0, 0, *e) for e in evs) + EV.pack(0, 0, 0, 0, 0))
for i, p in enumerate(sys.argv[1:]):
    x, y = map(int, p.split(","))
    emit([(3, 0x2f, 0), (3, 0x39, i + 1), (3, 0x35, x), (3, 0x36, y), (1, 0x14a, 1), (3, 0, x), (3, 1, y)])
    time.sleep(0.1)
    emit([(3, 0x2f, 0), (3, 0x39, -1), (1, 0x14a, 0)])
    time.sleep(1.5)
time.sleep(1)
