#!/usr/bin/env python3
"""Build HyperOS 4 (Xiaomi Pad 8 / yupei) system, system_ext, product EROFS images
for Lenovo TB710FU, reusing the HyperOS 3 port's vendor/odm/dlkm.

Inputs  : $TB_WORK/hyperos4_yupei/{x_*,img/*.img}   HyperOS 4 OTA (yupei), images + extracted trees
          $TB_WORK/port/{x_system_a,x_product_a,system_a.img}   the working HyperOS 3 port (extracted)
          $TB_WORK/overlay/*.apk                     overlays built from hyperos/overlay (signed by you)
          hyperos/ in this repository                keylayout, sepolicy_compat.cil
Outputs : $TB_WORK/build_os4/out/{system,system_ext,product}.img
TB_WORK defaults to ./work next to tools/.
"""
import json, os, shutil, subprocess, sys, tarfile, io, stat
sys.path.insert(0, os.path.dirname(__file__))
from erofs_meta import Erofs

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = os.path.abspath(os.environ.get('TB_WORK', os.path.join(REPO, 'work')))
Y = f'{H}/hyperos4_yupei'
PORT = f'{H}/port'
B = f'{H}/build_os4'
STAGE = f'{B}/stage'
OUT = f'{B}/out'
LOG = []


def log(*a):
    s = ' '.join(str(x) for x in a)
    LOG.append(s)
    print(s, flush=True)


def meta_of(img, cache):
    p = f'{B}/meta_{cache}.json'
    if not os.path.exists(p):
        json.dump(Erofs(img).walk(), open(p, 'w'))
    return json.load(open(p))


def clone_tree(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    subprocess.run(['cp', '-cR', src, dst], check=True)


def copy_in(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.isdir(src) and not os.path.islink(src):
        subprocess.run(['cp', '-cR', src, dst], check=True)
    else:
        subprocess.run(['cp', '-c', '-P', src, dst], check=True)


# ---------------------------------------------------------------- staging
def stage():
    os.makedirs(STAGE, exist_ok=True)
    for p in ('system', 'system_ext', 'product'):
        clone_tree(f'{Y}/x_{p}', f'{STAGE}/{p}')
    S, P = f'{STAGE}/system/system', f'{STAGE}/product'
    extra = {'system': {}, 'system_ext': {}, 'product': {}}   # rel path -> meta source

    # 1) mi_ext merged into product / system (as the HyperOS 3 port did)
    mi = f'{Y}/x_mi_ext'
    for root, dirs, files in os.walk(f'{mi}/product'):
        for n in files + [d for d in dirs if os.path.islink(os.path.join(root, d))]:
            src = os.path.join(root, n)
            rel = os.path.relpath(src, f'{mi}/product')
            dst = f'{P}/{rel}'
            if os.path.lexists(dst) and not os.path.isdir(dst):
                os.remove(dst)
            copy_in(src, dst)
            extra['product'][rel] = ('mi_ext', f'product/{rel}')
    for root, dirs, files in os.walk(f'{mi}/product'):
        for d in dirs:
            rel = os.path.relpath(os.path.join(root, d), f'{mi}/product')
            extra['product'].setdefault(rel, ('mi_ext', f'product/{rel}'))
    copy_in(f'{mi}/system/etc/permissions/privapp-permissions-system-miext.xml',
            f'{S}/etc/permissions/privapp-permissions-system-miext.xml')
    extra['system']['system/etc/permissions/privapp-permissions-system-miext.xml'] = \
        ('mi_ext', 'system/etc/permissions/privapp-permissions-system-miext.xml')

    # 2) product/pangu/system -> system (as the port did; drop TMS NFC jars)
    pg = f'{P}/pangu/system'
    for rel in ('app/Joyose', 'app/Joyose/Joyose.apk', 'etc/ota_skip_apps',
                'etc/permissions/privapp-permissions-pangu.xml',
                'etc/permissions/signature-permission-pangu.xml',
                'etc/permissions/security', 'etc/permissions/security/verity_key'):
        src = f'{pg}/{rel}'
        if os.path.isdir(src):
            os.makedirs(f'{S}/{rel}', exist_ok=True)
        else:
            copy_in(src, f'{S}/{rel}')
        extra['system'][f'system/{rel}'] = ('product', f'pangu/system/{rel}')
    shutil.rmtree(f'{P}/pangu')

    # 3) porter's lwky runtime tweaks from the working HyperOS 3 port
    PS = f'{PORT}/x_system_a/system'
    copy_in(f'{PS}/etc/init/init.lwky.rc', f'{S}/etc/init/init.lwky.rc')
    extra['system']['system/etc/init/init.lwky.rc'] = ('port', 'system/etc/init/init.lwky.rc')
    copy_in(f'{PS}/lwky', f'{S}/lwky')
    for root, dirs, files in os.walk(f'{PS}/lwky'):
        for n in dirs + files:
            rel = 'system/' + os.path.relpath(os.path.join(root, n), PS)
            extra['system'][rel] = ('port', rel)
    extra['system']['system/lwky'] = ('port', 'system/lwky')

    # 4) Lenovo Tab Pen Plus button key layout
    kl = 'system/usr/keylayout/Vendor_17ef_Product_617f.kl'
    copy_in(f'{REPO}/hyperos/keylayout/Vendor_17ef_Product_617f.kl', f'{STAGE}/system/{kl}')
    extra['system'][kl] = ('sibling', 'system/usr/keylayout/Generic.kl')

    # 5) USB NCM tethering overlay (usb0 interface)
    ov = 'overlay/TB710FUTetheringOverlay.apk'
    copy_in(f'{H}/overlay/TB710FUTetheringOverlay.apk', f'{P}/{ov}')
    extra['product'][ov] = ('sibling', 'overlay/NcmTetheringResCommon_Sys.apk')
    # EthernetTracker's default regex (usb|eth)\d+ grabs usb0 and its IpClient wipes the tether IPv4
    ov = 'overlay/TB710FUConnectivityOverlay.apk'
    copy_in(f'{H}/overlay/TB710FUConnectivityOverlay.apk', f'{P}/{ov}')
    extra['product'][ov] = ('sibling', 'overlay/NcmTetheringResCommon_Sys.apk')

    # 6) device features: odm reports ro.product.device=piano
    copy_in(f'{P}/etc/device_features/yupei.xml', f'{P}/etc/device_features/piano.xml')
    extra['product']['etc/device_features/piano.xml'] = ('product', 'etc/device_features/yupei.xml')

    # 6b) face unlock: yupei declares TEE face (needs Xiaomi's face HAL, absent on TB710FU -> enrollment fails).
    # Use the software 2D face unlock the HyperOS 3 port ships (PearlBiometric = com.miui.face, signed with the
    # same Xiaomi platform key as OS4); MiuiFaceManager takes the non-TEE path when support_tee_face_unlock=false.
    # oat/ is left out (compiled against the HyperOS 3 boot image). Meta (owner/mode/selinux) borrowed from app/MIUIXiaomiAccount.
    fx = f'{P}/etc/device_features/piano.xml'
    t = open(fx).read()
    assert '<bool name="support_tee_face_unlock">true</bool>' in t
    open(fx, 'w').write(t.replace('<bool name="support_tee_face_unlock">true</bool>',
                                  '<bool name="support_tee_face_unlock">false</bool>'))
    copy_in(f'{PORT}/x_product_a/app/PearlBiometric/PearlBiometric.apk', f'{P}/app/PearlBiometric/PearlBiometric.apk')
    extra['product']['app/PearlBiometric'] = ('product', 'app/MIUIXiaomiAccount')
    extra['product']['app/PearlBiometric/PearlBiometric.apk'] = ('product', 'app/MIUIXiaomiAccount/MIUIXiaomiAccount.apk')
    log('[product] face unlock: + app/PearlBiometric, support_tee_face_unlock=false')

    # 7) SELinux: re-declare types the Android 17 platform policy dropped but the API-34 vendor policy uses
    with open(f'{P}/etc/selinux/product_sepolicy.cil', 'a') as f:
        f.write('\n' + open(f'{REPO}/hyperos/sepolicy_compat.cil').read())

    # vendor has no media_profiles_vendor.xml -> zygote aborts in MediaProfiles (port comments it out too)
    bp = f'{S}/build.prop'
    t = open(bp).read()
    t = t.replace('\nmedia.settings.xml=/vendor/etc/media_profiles_vendor.xml', '\n#media.settings.xml=/vendor/etc/media_profiles_vendor.xml')
    open(bp, 'w').write(t)

    # 7b) Find Device: KEEP priv-app/MIUIFindDeviceCN. Its fid signing needs Xiaomi's TEE TA (cardapp, via mtd/
    # MTService), absent on Lenovo firmware, so it can never work -- but without the app com.xiaomi.account crashes
    # on re-auth (FindDeviceStatusManager "Can't bind service"). The failing status check is bypassed via the DEV
    # incremental set in edit_product_prop() (step 8). Do not turn on Find Device on the tablet.
    # TB_NO_FINDDEVICE=1: drop it for a first setup after a data wipe -- with the app present the setup wizard
    # demands an activation check that can never pass ("cloudsp_fid 参数不能为空", 10/20). Skip the Xiaomi account in
    # the wizard, then flash the normal product (with Find Device) and log in from Settings.
    if os.environ.get('TB_NO_FINDDEVICE'):
        shutil.rmtree(f'{P}/priv-app/MIUIFindDeviceCN', ignore_errors=True)
        log('[product] TB_NO_FINDDEVICE: - priv-app/MIUIFindDeviceCN')

    # debug variant (TB_DEBUG=1): adb without authorization from early boot, for logcat during hangs
    if os.environ.get('TB_DEBUG'):
        # the framework drops adb from the USB config after boot; put it back (vendor rc is sys.usb.config driven)
        rc = 'system/etc/init/tb710fu_adb.rc'
        open(f'{STAGE}/system/{rc}', 'w').write(
            'on property:sys.boot_completed=1 && property:sys.usb.config=mtp\n'
            '    setprop sys.usb.config mtp,adb\n\n'
            'on property:sys.boot_completed=1 && property:sys.usb.config=none\n'
            '    setprop sys.usb.config adb\n')
        extra['system'][rc] = ('sibling', 'system/etc/init/apexd.rc')
        bp = f'{S}/build.prop'
        t = open(bp).read()
        t = t.replace('ro.adb.secure=1', 'ro.adb.secure=0').replace('ro.debuggable=0', 'ro.debuggable=1')
        t += '\n# TB710FU debug build\npersist.sys.usb.config=adb\npersist.service.adb.enable=1\n'
        open(bp, 'w').write(t)
        log('[system] DEBUG build.prop: ro.debuggable=1 ro.adb.secure=0 persist.sys.usb.config=adb')
        # vendor/build.prop sets ro.adb.secure=1 and is loaded after system; product is loaded last
        open(f'{P}/etc/build.prop', 'a').write('\n# TB710FU debug build\nro.adb.secure=0\nro.debuggable=1\n')
        # /adb_keys -> /product/etc/security/adb_keys : trust the build host's adb key
        ak = f'{P}/etc/security/adb_keys'
        os.makedirs(os.path.dirname(ak), exist_ok=True)
        old = open(ak).read() if os.path.exists(ak) else ''
        open(ak, 'w').write(old + open(os.path.expanduser('~/.android/adbkey.pub')).read())
        extra['product'].setdefault('etc/security/adb_keys', ('sibling', 'etc/build.prop'))
        log('[product] DEBUG: ro.adb.secure=0, adb_keys added')

    # 8) product build.prop
    edit_product_prop(f'{P}/etc/build.prop', f'{mi}/etc/build.prop')
    json.dump(extra, open(f'{B}/extra_meta.json', 'w'), indent=1)
    return extra


def edit_product_prop(path, miext_prop):
    lines = open(path).read().splitlines()
    drop = {'ro.product.build.no_bionic_page_size_macro', 'ro.sf.lcd_density'}
    set_ = {'ro.product.cpu.pagesize.max': '4096'}
    # ".DEV" suffix -> miui.os.Build.IS_STABLE_VERSION=false -> Xiaomi Account's isIgnoreExceptionBuild() ignores the
    # Find Device status check error ("查找Pad检查状态出错"), which always fails without Xiaomi's TEE (see step 7b).
    # Replaces every occurrence (product build.prop defines it twice; product is loaded last, so it wins).
    override = {'ro.build.version.incremental': lambda v: v if v.endswith('.DEV') else v + '.DEV'}
    out = []
    for l in lines:
        k = l.split('=', 1)[0] if '=' in l and not l.startswith('#') else None
        if k in drop:
            out.append('# removed for TB710FU: ' + l)
            continue
        if k in override:
            out.append(f'{k}={override[k](l.split("=", 1)[1])}')
            continue
        if k in set_:
            out.append(f'{k}={set_.pop(k)}')
            continue
        out.append(l)
    out.append('')
    out.append('# ---- merged from mi_ext/etc/build.prop ----')
    for l in open(miext_prop).read().splitlines():
        if not l or l.startswith('#'):
            continue
        k = l.split('=', 1)[0]
        if k in ('ro.vendor.build.ab_ota_partitions',):
            continue
        if k == 'ro.product.mod_device':
            l = 'ro.product.mod_device=piano'
        out.append(l)
    out += ['', '# ---- Lenovo TB710FU port ----',
            'lwky.hyper.brand=Lenovo', 'lwky.hyper.device=TB710FU', 'lwky.hyper.manufacturer=LENOVO',
            'lwky.hyper.marketname=联想小新平板 Pro GT', 'lwky.hyper.model=TB710FU',
            'lwky.hyper.vendor.brand=Lenovo', 'lwky.hyper.vendor.device=TB710FU',
            'lwky.hyper.vendor.manufacturer=LENOVO', 'lwky.hyper.vendor.model=TB710FU',
            'lwky.hyper.vendor.name=TB710FU',
            'persist.sys.stylus.enable=1',
            # AirPlay receiver colours: Skia/Vulkan TextureView YUV->RGB is BT.601-limited (Step 15); was a Magisk module
            'debug.hwui.renderer=skiagl',
            'persist.vendor.battery.health=true', 'persist.vendor.battery.health.optimise=true',
            'persist.vendor.night.charge=true', 'persist.vendor.smartchg=30',
            'persist.vendor.smart.battMntor.V2=true', 'persist.vendor.hightemp.notice=true',
            '']
    open(path, 'w').write('\n'.join(out))


# ---------------------------------------------------------------- tar + mkfs
def default_meta(rel, is_dir, parent):
    m = dict(parent) if parent else dict(uid=0, gid=0, xattrs={})
    m['mode'] = (0o040755 if is_dir else 0o100644)
    m['xattrs'] = {k: v for k, v in m.get('xattrs', {}).items() if k == 'security.selinux'}
    return m


def build_tar(part, extra, metas):
    base = metas[f'y_{part}']
    srcmap = {'mi_ext': metas['y_mi_ext'], 'product': metas['y_product'], 'port': metas['port_system']}
    root = f'{STAGE}/{part}'
    tpath = f'{B}/{part}.tar'
    t = tarfile.open(tpath, 'w', format=tarfile.PAX_FORMAT, encoding='utf-8', errors='surrogateescape')
    missing = 0
    entries = ['.']
    for r, dirs, files in os.walk(root):
        dirs.sort(); files.sort()
        for n in dirs + files:
            entries.append(os.path.relpath(os.path.join(r, n), root))
    for rel in entries:
        full = os.path.join(root, rel)
        st = os.lstat(full)
        m = None
        if rel in extra.get(part, {}):
            kind, src = extra[part][rel]
            if kind == 'sibling':
                m = dict(base.get(src) or {})
                m['mode'] = 0o100644
            elif kind == 'mi_ext' and stat.S_ISDIR(st.st_mode) and rel in base:
                m = base[rel]          # keep product's own directory metadata
            else:
                m = srcmap[kind].get(src)
        if m is None:
            m = base.get(rel)
        if m is None:
            parent = base.get(os.path.dirname(rel) or '.')
            m = default_meta(rel, stat.S_ISDIR(st.st_mode), parent)
            missing += 1
            if missing <= 30:
                log(f'  [{part}] no meta, default for {rel}')
        ti = tarfile.TarInfo('./' + rel if rel != '.' else '.')
        ti.uid, ti.gid = m['uid'], m['gid']
        ti.mode = m['mode'] & 0o7777
        ti.mtime = 1230768000
        ti.pax_headers = {f'SCHILY.xattr.{k}': bytes.fromhex(v).decode('utf-8', 'surrogateescape')
                          for k, v in m.get('xattrs', {}).items()}
        if stat.S_ISLNK(st.st_mode):
            ti.type = tarfile.SYMTYPE
            ti.linkname = os.readlink(full)
            t.addfile(ti)
        elif stat.S_ISDIR(st.st_mode):
            ti.type = tarfile.DIRTYPE
            t.addfile(ti)
        else:
            ti.type = tarfile.REGTYPE
            ti.size = st.st_size
            with open(full, 'rb') as fh:
                t.addfile(ti, fh)
    t.close()
    log(f'[{part}] tar entries={len(entries)} defaulted={missing}')
    return tpath


def mkfs(part, tpath):
    os.makedirs(OUT, exist_ok=True)
    img = f'{OUT}/{part}.img'
    if os.path.exists(img):
        os.remove(img)
    subprocess.run(['mkfs.erofs', '-b4096', '-zlz4hc,9', '-T1230768000', '--tar=f', img, tpath],
                   check=True, stdout=subprocess.DEVNULL)
    log(f'[{part}] image {os.path.getsize(img)/1e9:.3f} GB')
    os.remove(tpath)
    return img


def main():
    parts = sys.argv[1:] or ['system', 'system_ext', 'product']
    metas = {f'y_{p}': meta_of(f'{Y}/img/{p}.img', f'y_{p}') for p in ('system', 'system_ext', 'product', 'mi_ext')}
    metas['port_system'] = meta_of(f'{PORT}/system_a.img', 'port_system')
    extra = stage()
    for p in parts:
        mkfs(p, build_tar(p, extra, metas))
    open(f'{B}/build.log', 'w').write('\n'.join(LOG))


if __name__ == '__main__':
    main()
