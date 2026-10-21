#!/bin/sh
# kshim_variants.sh NAME IMAGE DTB
# Pack the two kShimC boot images for boot_a: menu default HyperOS and menu default Linux.
#   -> $OUT/NAME_{android,linux}/boot.img and $OUT/current/boot_{android,linux}.img
# Each one is checked against your own vbmeta_a (AVB chain) before it is copied to current/.
#
# Inputs (environment, all files from YOUR device):
#   STOCK_BOOT   boot_a dump of the working HyperOS boot chain   (default work/stock/boot_a.img)
#   VBMETA       vbmeta_a dump                                   (default work/stock/vbmeta_a.img)
#   SHIM         kShimC binary built from kshim/                 (default work/kshim/kShimC.bin)
#   OUT          output directory                                (default work/boot)
#   LINUX_NAME   menu entry for the Linux kernel                 (default SteamOS)
set -e
cd "$(dirname "$0")/.."
N=${1:?usage: kshim_variants.sh NAME IMAGE DTB}; IMG=${2:?}; DTB=${3:?}
STOCK_BOOT=${STOCK_BOOT:-work/stock/boot_a.img}; VBMETA=${VBMETA:-work/stock/vbmeta_a.img}
SHIM=${SHIM:-work/kshim/kShimC.bin}; OUT=${OUT:-work/boot}; PY=${PYTHON:-python3}
V=$(mktemp -d); trap 'rm -rf "$V"' EXIT; cp "$VBMETA" "$V/vbmeta.img"
mkdir -p "$OUT/current"
for d in android linux; do
  ok=0
  for t in 1 2 3; do   # the DBKP packer fails now and then (exit 234); retry
    if $PY tools/kshim_pack_boot.py --boot "$STOCK_BOOT" --shim "$SHIM" \
        --out "$OUT/${N}_$d" --probe-slots --timeout-ms 8000 --linux "$IMG" --dtb "$DTB" \
        --linux-name "${LINUX_NAME:-SteamOS}" --default $d > "$V/pack.log" 2>&1; then ok=1; break; fi
    sleep 3
  done
  [ $ok = 1 ] || { cat "$V/pack.log"; exit 1; }
  cp "$OUT/${N}_$d/boot.img" "$V/boot.img"
  $PY tools/avb/avbtool.py verify_image --image "$V/vbmeta.img" --key tools/avb/testkey_rsa4096.pem \
     --follow_chain_partitions 2>&1 | grep -q "^boot: Successfully verified" || { echo "AVB verify failed ($d)"; exit 1; }
  cp "$OUT/${N}_$d/boot.img" "$OUT/current/boot_$d.img"
  echo "$d: $(shasum -a 256 "$OUT/current/boot_$d.img" | cut -c1-16) (avb ok)"
done
