# list apps in Steam's appinfo.vdf (v29, string table) with linux arm64 depots or launch entries
import struct, sys
d = open(sys.argv[1], "rb").read()
magic, uni = struct.unpack_from("<II", d, 0)
strtab_off, = struct.unpack_from("<q", d, 8)
n, = struct.unpack_from("<I", d, strtab_off); p = strtab_off + 4; S = []
for _ in range(n):
    e = d.index(b"\0", p); S.append(d[p:e].decode("utf-8", "replace")); p = e + 1
def kv(p):
    out = {}
    while True:
        t = d[p]; p += 1
        if t == 8: return out, p
        k = S[struct.unpack_from("<I", d, p)[0]]; p += 4
        if t == 0: v, p = kv(p)
        elif t == 1: e = d.index(b"\0", p); v = d[p:e].decode("utf-8", "replace"); p = e + 1
        elif t == 2: v = struct.unpack_from("<i", d, p)[0]; p += 4
        elif t == 7: v = struct.unpack_from("<Q", d, p)[0]; p += 8
        else: raise ValueError(t)
        out[k] = v
p = 16; res = []
while p < strtab_off:
    appid, size = struct.unpack_from("<II", d, p)
    if appid == 0: break
    start = p + 8; body = start + 4 + 4 + 8 + 20 + 4 + 20
    try:
        a, _ = kv(body)
    except Exception:
        p = start + size; continue
    a = a.get("appinfo", a); com = a.get("common", {})
    typ = str(com.get("type", "")).lower(); name = com.get("name", "")
    hits = set()
    for k, dep in (a.get("depots") or {}).items():
        if isinstance(dep, dict):
            c = dep.get("config", {}) or {}
            if "linux" in str(c.get("oslist", "")) and "arm64" in str(c.get("osarch", "")): hits.add("depot")
    for k, l in ((a.get("config") or {}).get("launch") or {}).items():
        c = (l.get("config") or {}) if isinstance(l, dict) else {}
        if "linux" in str(c.get("oslist", "")) and "arm64" in str(c.get("osarch", "")): hits.add("launch")
    if hits and typ in ("game", "demo", "application"): res.append((appid, typ, name, ",".join(sorted(hits))))
    p = start + size
for r in sorted(res, key=lambda r: r[2].lower()): print(*r, sep="\t")
print("total", len(res), file=sys.stderr)
