# absinfo.py /dev/input/eventX ...  - print EVIOCGABS (value min max fuzz flat resolution) for the usual axes
import fcntl, array, sys
for dev in sys.argv[1:]:
    fd = open(dev, "rb")
    for code in (0, 1, 0x18, 0x19, 0x1a, 0x1b, 0x35, 0x36):
        buf = array.array("i", [0] * 6)
        try:
            fcntl.ioctl(fd, 0x80184540 + code, buf)
            print(dev, hex(code), "val,min,max,fuzz,flat,res =", list(buf))
        except OSError:
            pass
