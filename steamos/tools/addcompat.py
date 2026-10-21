# addcompat.py config.vdf tool id,id,...  : add/replace CompatToolMapping entries
import sys, re
p, tool, ids = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
L = open(p, encoding="utf-8").read().split("\n")
i = next(k for k, l in enumerate(L) if l.strip() == '"CompatToolMapping"')
ind = L[i][:len(L[i]) - len(L[i].lstrip())]; assert L[i + 1].strip() == "{"
# end of block
j = i + 2
while L[j] != ind + "}": j += 1
existing = {}
k = i + 2
while k < j:
    m = re.match(r'^\t+"(\d+)"$', L[k])
    if m and L[k].startswith(ind + "\t\"") :
        e = k + 1
        while L[e] != ind + "\t}": e += 1
        existing[m.group(1)] = (k, e); k = e + 1
    else: k += 1
added, changed = [], []
for a in ids:
    if a in existing:
        s, e = existing[a]
        for x in range(s, e):
            if L[x].strip().startswith('"name"'):
                if tool not in L[x]: L[x] = f'{ind}\t\t"name"\t\t"{tool}"'; changed.append(a)
        continue
    block = [f'{ind}\t"{a}"', f"{ind}\t{{", f'{ind}\t\t"name"\t\t"{tool}"', f'{ind}\t\t"config"\t\t""', f'{ind}\t\t"priority"\t\t"250"', f"{ind}\t}}"]
    L[j:j] = block; j += len(block); added.append(a)
open(p, "w", encoding="utf-8").write("\n".join(L))
print("existing:", sorted(existing, key=int)); print("added", len(added), "changed", changed)
