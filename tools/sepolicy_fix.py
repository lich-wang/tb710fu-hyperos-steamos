#!/usr/bin/env python3
"""Iteratively compile the combined SELinux policy (as Android init does) and, for every
type the vendor policy references but the new platform policy no longer declares,
re-declare it from the old (HyperOS 3) policies into hyperos/sepolicy_compat.cil."""
import os, re, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = os.path.abspath(os.environ.get('TB_WORK', os.path.join(REPO, 'work')))
S = f'{H}/build_os4/stage'
A = f'{H}/port'
# secilc from SELinux userspace (libsepol/cil), built for the host
SECILC = os.environ.get('SECILC', 'secilc')
COMPAT = f'{REPO}/hyperos/sepolicy_compat.cil'
OS3 = [f'{A}/x_system_a/system/etc/selinux/plat_sepolicy.cil',
       f'{A}/x_system_ext_a/etc/selinux/system_ext_sepolicy.cil',
       f'{A}/x_product_a/etc/selinux/product_sepolicy.cil']
VV = open(f'{A}/vendor_x/etc/selinux/plat_sepolicy_vers.txt').read().strip()
INPUTS = [f'{S}/system/system/etc/selinux/plat_sepolicy.cil',
          f'{S}/system/system/etc/selinux/mapping/{VV}.cil',
          f'{S}/system/system/etc/selinux/mapping/{VV}.compat.cil',
          f'{S}/system_ext/etc/selinux/system_ext_sepolicy.cil',
          f'{S}/system_ext/etc/selinux/mapping/{VV}.cil',
          f'{S}/product/etc/selinux/product_sepolicy.cil',
          f'{S}/product/etc/selinux/mapping/{VV}.cil',
          COMPAT,
          f'{A}/vendor_x/etc/selinux/plat_pub_versioned.cil',
          f'{A}/vendor_x/etc/selinux/vendor_sepolicy.cil']
INPUTS = [p for p in INPUTS if os.path.exists(p) or p == COMPAT]

os3_text = '\n'.join(open(p).read() for p in OS3)


def new_text():
    return '\n'.join(open(p).read() for p in INPUTS if p != COMPAT and os.path.exists(p))


def compile_once():
    r = subprocess.run([SECILC, '-m', '-M', 'true', '-G', '-N', '-c', '33',
                        '-o', '/tmp/tb710fu-sepolicy.bin', '-f', '/dev/null'] + INPUTS,
                       capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)


def unresolved_names(err):
    """Locate the failing statement and return identifiers in it that nothing declares."""
    m = re.search(r'at (\S+):(\d+)', err)
    if not m:
        return []
    line = open(m.group(1)).read().splitlines()[int(m.group(2)) - 1]
    decl_re = re.compile(r'\((?:type|typeattribute|typealias)\s+([^\s()]+)\)')
    declared = set(decl_re.findall(new_text())) | set(decl_re.findall(open(COMPAT).read()))
    toks = dict.fromkeys(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', line))
    missing = [t for t in toks if t not in declared and
               re.search(r'\((?:type|typeattribute)\s+' + re.escape(t) + r'\)', os3_text)]
    return missing, line


def declare(t, new):
    out = []
    if re.search(r'\(typeattribute ' + re.escape(t) + r'\)', os3_text):
        out.append(f'(typeattribute {t})')
    else:
        out += [f'(type {t})', f'(roletype object_r {t})']
    for m in re.finditer(r'\(typeattributeset (\S+) \(([^()]*)\)\)', os3_text):
        attr, members = m.group(1), m.group(2).split()
        if t in members and re.search(r'\(typeattribute ' + re.escape(attr) + r'\)', new):
            out.append(f'(typeattributeset {attr} ({t}))')
    return out


def main():
    if not os.path.exists(COMPAT):
        open(COMPAT, 'w').write('; TB710FU compat: types dropped from the Android 17 platform policy '
                                'but still used by the API-34 vendor policy\n')
    new = new_text()
    for i in range(200):
        rc, err = compile_once()
        if rc == 0:
            print(f'COMPILE OK after {i} fix rounds')
            return 0
        names, line = unresolved_names(err)
        if not names:
            print('cannot auto-fix:\n', err.strip()[-800:], '\n  statement:', line)
            return 1
        lines = []
        for t in names:
            lines += declare(t, new)
        print('round', i, 'declare', names)
        with open(COMPAT, 'a') as f:
            f.write('\n'.join(lines) + '\n')
    return 1


if __name__ == '__main__':
    sys.exit(main())
