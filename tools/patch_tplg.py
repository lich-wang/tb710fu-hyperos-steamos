#!/usr/bin/env python3
"""patch_tplg.py IN OUT - turn the TB710FU AudioReach topology's speaker endpoint into TDM.

tb710fu-linux ships Lenovo-TB710FU-tplg.bin with an I2S_SINK module (0x0700100A) on the
secondary TDM path; the ADSP rejects 4ch/32bit on I2S. HyperOS uses TDM_SINK (0x0700100E)
there (seen in its ACDB / libagm). The module id appears exactly once: replace it in place.
"""
import struct, sys
src, dst = sys.argv[1:3]
d = bytearray(open(src, "rb").read())
old, new = struct.pack("<I", 0x0700100A), struct.pack("<I", 0x0700100E)
n_old, n_new = d.count(old), d.count(new)
if n_old == 0 and n_new == 1:
    sys.exit("already patched")
if n_old != 1:
    sys.exit(f"expected exactly one I2S_SINK id, found {n_old}: not the expected topology")
i = d.find(old)
d[i:i + 4] = new
open(dst, "wb").write(d)
print(f"patched I2S_SINK -> TDM_SINK at offset {i:#x}")
