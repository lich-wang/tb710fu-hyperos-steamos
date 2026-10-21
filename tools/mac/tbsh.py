#!/usr/bin/env python3
"""Run shell commands on the TB710FU Linux diagnostic initramfs (busybox telnetd, no auth).
usage: tbsh.py 'cmd; cmd' [timeout_s]"""
import socket, sys, time
IAC = 255
def strip(b):
    out = bytearray(); i = 0
    while i < len(b):
        if b[i] == IAC and i + 1 < len(b):
            i += 3 if b[i + 1] in (251, 252, 253, 254) else 2
            continue
        out.append(b[i]); i += 1
    return out.decode(errors="replace")
cmd = sys.argv[1]; tmo = float(sys.argv[2]) if len(sys.argv) > 2 else 15
s = socket.create_connection(("172.16.42.1", 23), timeout=5)
s.settimeout(0.5); time.sleep(0.5)
try: s.recv(4096)
except socket.timeout: pass
mark = "__TBDONE__"
s.sendall((cmd + "; echo " + mark + "\n").encode())
buf = b""; end = time.time() + tmo
while time.time() < end:
    try:
        d = s.recv(65536)
        if not d: break
        buf += d
        if strip(buf).count(mark) >= 2: break
    except socket.timeout: pass
txt = strip(buf)
lines = txt.splitlines()
print("\n".join(l for l in lines[1:] if mark not in l and not l.startswith("~ #")))
s.close()
