#!/usr/bin/env python3
"""Pack a kShimC runtime + the current Android kernel into a TB710FU boot.img.

Steps:
  1. take the raw GKI Image out of the current boot.img (boot v4, page 4096)
  2. run the DualBootKernelPatcher packer (built in the kshim-build docker image)
     on a base-only config: [Image-00 = Android, BaseImage] + auto-attached shim
  3. rebuild boot.img with the packed kernel (original header, kernel_size patched;
     optional gzip of the packed kernel)
  4. add an AVB hash footer signed with testkey_rsa4096 (same salt / rollback index
     / props as the original footer), so the existing vbmeta_a chain still accepts it

Usage: kshim_pack_boot.py --boot boot_a.img --shim kShimC.bin --out DIR [--gzip]
"""
import argparse
import gzip
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# AOSP external/avb: avbtool.py + test/data/testkey_rsa4096.pem (not shipped here)
AVBTOOL = os.path.join(HERE, "avb", "avbtool.py")
TESTKEY = os.path.join(HERE, "avb", "testkey_rsa4096.pem")
PY = sys.executable
PAGE = 4096
PART_SIZE = 100663296
# DualBootKernelPatcher checkout with its packer built (see kshim/README.md)
DBKP_BUILD = os.path.abspath(os.environ.get("KSHIM_BUILD", os.path.join(HERE, "..", "work", "kshim-build")))


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def avb_info(path):
    return subprocess.check_output([PY, AVBTOOL, "info_image", "--image", path], text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", required=True)
    ap.add_argument("--shim", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--gzip", action="store_true")
    ap.add_argument("--timeout-ms", type=int, default=8000)
    ap.add_argument("--linux", help="extra Linux entry: raw arm64 Image")
    ap.add_argument("--dtb", help="DTB for the --linux entry")
    ap.add_argument("--linux-name", default="Linux")
    ap.add_argument("--default", choices=["android", "linux"], default="android",
                    help="menu entry booted when the countdown expires")
    ap.add_argument("--probe-slots", action="store_true",
                    help="add kshimreport/androidboot.kshim_s1..s8 'pending' placeholders to the "
                         "boot header cmdline (RESOURCES_ONLY diagnostic reports)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    boot = open(a.boot, "rb").read()
    assert boot[:8] == b"ANDROID!"
    kernel_size, ramdisk_size, os_version, header_size = struct.unpack_from("<IIII", boot, 8)
    header_version = struct.unpack_from("<I", boot, 40)[0]
    sig_size = struct.unpack_from("<I", boot, 1580)[0]
    assert header_version == 4 and ramdisk_size == 0 and sig_size == 0, (header_version, ramdisk_size, sig_size)
    kernel = boot[PAGE:PAGE + kernel_size]
    assert kernel[56:60] == b"ARM\x64", "base kernel must be a raw arm64 Image"

    # 2. pack (packer runs in docker; paths are under /w = DBKP_BUILD)
    work = os.path.join(DBKP_BUILD, "pack")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    open(os.path.join(work, "Image.android"), "wb").write(kernel)
    shutil.copy(a.shim, os.path.join(work, "kShimC.bin"))
    default = "Image-01" if (a.default == "linux" and a.linux) else "Image-00"
    cfg = ["[Pack]", "Shim=kShimC.bin", "Output=PackedKernel", "Default=" + default,
           "Timeout=%d" % a.timeout_ms, "",
           "[Image-00]", "Name=HyperOS", "Path=Image.android", "Type=Linux",
           "BaseImage=true", "Align=21", ""]
    if a.linux:
        # Image-01 = Linux (raw Image, own DTB); Image-02 = its DTB
        lk = open(a.linux, "rb").read()
        assert lk[56:60] == b"ARM\x64", "--linux must be a raw arm64 Image"
        shutil.copy(a.linux, os.path.join(work, "Image.linux"))
        shutil.copy(a.dtb, os.path.join(work, "linux.dtb"))
        cfg += ["[Image-01]", "Name=" + a.linux_name, "Path=Image.linux", "Type=Linux",
                "BaseImage=false", "Align=21", "DeviceTreeBlob=Image-02", "",
                "[Image-02]", "Name=" + a.linux_name + " DTB", "Path=linux.dtb", "Type=DTB",
                "BaseImage=false", ""]
    cfg += ["[Manifest]", "Type=Manifest", ""]
    open(os.path.join(work, "build.cfg"), "w").write("\n".join(cfg))
    packer = subprocess.check_output(
        ["sh", "-c", "find %s/DBKP/build -maxdepth 2 -type f -perm -u+x -name '*Patcher*' | head -1" % DBKP_BUILD],
        text=True).strip()
    assert packer, "packer binary not built"
    rel = os.path.relpath(packer, DBKP_BUILD)
    subprocess.run(["docker", "run", "--rm", "-v", DBKP_BUILD + ":/w", "-w", "/w/pack",
                    "kshim-build", "/w/" + rel, "build.cfg"], check=True)
    packed = open(os.path.join(work, "PackedKernel"), "rb").read()
    assert packed[56:60] == b"ARM\x64"
    payload = gzip.compress(packed, compresslevel=9, mtime=0) if a.gzip else packed

    # 3. rebuild boot.img: original header page, new kernel_size, kernel padded to PAGE
    hdr = bytearray(boot[:PAGE])
    struct.pack_into("<I", hdr, 8, len(payload))
    if a.probe_slots:
        # kShimC fills these in place (fixed 80-byte values) in /chosen/bootargs;
        # Android then sees androidboot.kshim_probe / kshim_s0..s8.
        pend = "pending" + "_" * 73
        params = ["kshimreport.kshim_probe=" + pend, "kshimreport.kshim_s0=" + pend]
        params += ["androidboot.kshim_s%d=%s" % (i, pend) for i in range(1, 9)]
        old = bytes(hdr[44:1580]).split(b"\0", 1)[0]
        text = ((old + b" ") if old else b"") + " ".join(params).encode()
        assert len(text) < 1536
        hdr[44:1580] = text + b"\0" * (1536 - len(text))
    body = bytes(hdr) + payload + b"\0" * (-len(payload) % PAGE)
    assert len(body) < PART_SIZE - 1024 * 1024, "boot image too large"
    out_img = os.path.join(a.out, "boot.img")
    open(out_img, "wb").write(body)

    # 4. AVB hash footer, signed like the original
    info = avb_info(a.boot)
    salt = re.search(r"Salt:\s+([0-9a-f]+)", info).group(1)
    rb = re.search(r"Rollback Index:\s+(\d+)", info).group(1)
    props = re.findall(r"Prop: (\S+) -> '([^']*)'", info)
    cmd = [PY, AVBTOOL, "add_hash_footer", "--image", out_img, "--partition_name", "boot",
           "--partition_size", str(PART_SIZE), "--key", TESTKEY, "--algorithm", "SHA256_RSA4096",
           "--rollback_index", rb, "--salt", salt]
    seen = set()
    for k, v in props:
        if (k, v) in seen:
            continue
        seen.add((k, v))
        cmd += ["--prop", "%s:%s" % (k, v)]
    subprocess.run(cmd, check=True)

    print("base kernel  %d bytes sha256 %s" % (len(kernel), hashlib.sha256(kernel).hexdigest()))
    print("packed       %d bytes sha256 %s" % (len(packed), hashlib.sha256(packed).hexdigest()))
    print("payload      %d bytes (%s)" % (len(payload), "gzip" if a.gzip else "raw"))
    print("boot.img     %s sha256 %s" % (out_img, sha(out_img)))


if __name__ == "__main__":
    sys.exit(main())
