#!/usr/bin/env python3
"""Build the "v3" boot chain for slot A of a locked TB710FU running the HyperOS 3 port.

Input : the port author's original boot.img, init_boot.img, dtbo.img, vendor_boot.img
        (inside the HyperOS 3 port zip; kernel 6.1.128 = matches the modules in its super,
        vendor_boot fstab has ext4+erofs entries for every logical partition)
Output: OUT/{boot,init_boot,dtbo,vendor_boot,vbmeta}.img

- boot, init_boot, dtbo are used as they are.
- vendor_boot: the author's footer hash is stale -> erase_footer, then add_hash_footer again
  with the same salt and properties (no key; its digest goes into vbmeta).
- vbmeta: AOSP testkey_rsa4096, flags=1 (hashtree disabled), chain boot (loc 3, rsa4096),
  recovery (loc 1, rsa4096), vbmeta_system (loc 2, rsa2048), plus the hash descriptors of
  dtbo, init_boot, vendor_boot. The locked ABL of this tablet trusts the AOSP test keys.
- vbmeta_system, pvmfw, recovery stay the ones on the device (ZUI 495 / the WITHOUT_UBL
  package): they carry the rollback indexes the device already has (vbmeta_system 1783209600).

Needs AOSP avbtool + test keys in tools/avb/.
"""
import argparse, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
AVB = os.path.join(HERE, "avb")
AVBTOOL = [sys.executable, os.path.join(AVB, "avbtool.py")]
K4096 = os.path.join(AVB, "testkey_rsa4096.pem")
K2048 = os.path.join(AVB, "testkey_rsa2048.pem")
PART = {"vendor_boot": 100663296}


def avb(*a, **kw):
    return subprocess.run(AVBTOOL + list(a), check=True, text=True, capture_output=True, **kw).stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="directory with the author's boot/init_boot/dtbo/vendor_boot.img")
    ap.add_argument("out", help="output directory")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for n in ("boot", "init_boot", "dtbo"):
        shutil.copyfile(os.path.join(a.src, n + ".img"), os.path.join(a.out, n + ".img"))

    # vendor_boot: re-footer with the original salt and props
    vb = os.path.join(a.out, "vendor_boot.img")
    shutil.copyfile(os.path.join(a.src, "vendor_boot.img"), vb)
    info = avb("info_image", "--image", vb)
    salt = re.search(r"Salt:\s+([0-9a-f]+)", info).group(1)
    props = re.findall(r"Prop: (\S+) -> '([^']*)'", info)
    avb("erase_footer", "--image", vb)
    cmd = ["add_hash_footer", "--image", vb, "--partition_name", "vendor_boot",
           "--partition_size", str(PART["vendor_boot"]), "--salt", salt]
    for k, v in props:
        cmd += ["--prop", f"{k}:{v}"]
    avb(*cmd)

    # vbmeta
    with tempfile.TemporaryDirectory() as t:
        pk4, pk2 = os.path.join(t, "pk4096.bin"), os.path.join(t, "pk2048.bin")
        avb("extract_public_key", "--key", K4096, "--output", pk4)
        avb("extract_public_key", "--key", K2048, "--output", pk2)
        avb("make_vbmeta_image", "--output", os.path.join(a.out, "vbmeta.img"),
            "--key", K4096, "--algorithm", "SHA256_RSA4096", "--flags", "1", "--padding_size", "4096",
            "--chain_partition", f"boot:3:{pk4}", "--chain_partition", f"recovery:1:{pk4}",
            "--chain_partition", f"vbmeta_system:2:{pk2}",
            "--include_descriptors_from_image", os.path.join(a.out, "dtbo.img"),
            "--include_descriptors_from_image", os.path.join(a.out, "init_boot.img"),
            "--include_descriptors_from_image", vb)
    for n in ("boot", "init_boot", "dtbo", "vendor_boot"):
        avb("verify_image", "--image", os.path.join(a.out, n + ".img"))
    print("v3 boot chain in", a.out)
    for n in ("boot", "init_boot", "dtbo", "vendor_boot", "vbmeta"):
        p = os.path.join(a.out, n + ".img")
        print(f"  {n + '.img':16s} {os.path.getsize(p):>10d}")


if __name__ == "__main__":
    main()
