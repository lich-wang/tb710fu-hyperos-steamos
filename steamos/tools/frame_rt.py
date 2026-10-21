# frame_rt.py appinfo.vdf steamapps_dir : per game -> how Steam Frame (arm64) would run it
import sys, os, re, collections
# reuse the appinfo.vdf parser from arm64apps.py
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "arm64apps.py")).read().split("p = 16; res = []")[0])
installed = {int(m.group(1)) for f in os.listdir(sys.argv[2]) if (m := re.match(r"appmanifest_(\d+)\.acf", f))}
p = 16; rows = []
while p < strtab_off:
    appid, size = struct.unpack_from("<II", d, p)
    if appid == 0: break
    start = p + 8; body = start + 4 + 4 + 8 + 20 + 4 + 20
    try: a, _ = kv(body)
    except Exception: p = start + size; continue
    a = a.get("appinfo", a); com = a.get("common", {})
    if str(com.get("type", "")).lower() == "game":
        sfc = com.get("steam_frame_compatibility") or {}
        rec = (sfc.get("configuration") or {}).get("recommended_runtime", "") if isinstance(sfc, dict) else ""
        cat = sfc.get("category", "") if isinstance(sfc, dict) else ""
        maps = [str(m.get("tool", "")) for m in ((a.get("config") or {}).get("app_mappings") or {}).values() if isinstance(m, dict)]
        native = any("arm64" in m and "proton" not in m for m in maps) or "linux" in str(rec) and "arm" in str(rec)
        android = any("lepton" in m for m in maps) or "lepton" in str(rec)
        if rec or maps:
            rows.append((("*" if appid in installed else " "), appid, com.get("name", ""), rec, cat, ",".join(maps), "NATIVE-ARM64" if native else ("ANDROID" if android else "")))
    p = start + size
for r in sorted(rows, key=lambda r: (r[6] == "", r[2].lower())): print(*r, sep="\t")
print("rows", len(rows), collections.Counter(r[3] for r in rows), file=sys.stderr)
