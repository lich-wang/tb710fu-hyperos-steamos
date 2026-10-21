# evrec.py SECONDS /dev/input/eventX ...  - count input events per device and show the first few (type, code, value)
import struct, select, time, sys
devs = {p: open(p, "rb", buffering=0) for p in sys.argv[2:]}
end = time.time() + float(sys.argv[1]); n = {p: 0 for p in devs}; first = {}
while time.time() < end:
    r, _, _ = select.select(list(devs.values()), [], [], 0.5)
    for f in r:
        d = f.read(24 * 64)
        p = [k for k, v in devs.items() if v is f][0]
        for i in range(0, len(d), 24):
            _, _, t, c, v = struct.unpack("qqHHi", d[i:i+24])
            n[p] += 1
            if p not in first or len(first[p]) < 12: first.setdefault(p, []).append((t, c, v))
print(n); print(first)
