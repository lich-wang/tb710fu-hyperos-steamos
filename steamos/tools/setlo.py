# setlo.py localconfig.vdf APPID 'launch options'  - set a game's Steam launch options (stop steam.service first)
import sys, re
p, app, opts = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(p, encoding="utf-8").read().split("\n")
for i, l in enumerate(lines):
    if l.strip() == f'"{app}"' and lines[i + 1].strip() == "{" and l.startswith("\t\t\t\t\t"):
        ind = l[:len(l) - len(l.lstrip())] + "\t"
        j = i + 2
        while lines[j].strip() != "}" or not lines[j].startswith(ind[:-1] + "}"):
            if lines[j].strip().startswith('"LaunchOptions"') and lines[j].startswith(ind + '"'):
                del lines[j]; continue
            j += 1
        esc = opts.replace("\\", "\\\\").replace('"', '\\"')
        lines.insert(i + 2, f'{ind}"LaunchOptions"\t\t"{esc}"')
        open(p, "w", encoding="utf-8").write("\n".join(lines))
        print("set at line", i + 3); break
else:
    sys.exit("app block not found")
