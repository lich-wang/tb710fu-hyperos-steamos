#!/bin/bash
# collect_firmware.sh OUT_DIR
# Copy this tablet's own firmware out of HyperOS (adb + Magisk root) into a tree laid out
# like /usr/lib/firmware, for steamos/install_payload.sh. See docs/firmware.md for the files
# that come from linux-firmware / tb710fu-linux instead (GPU sqe/aqe/gmu, WiFi, Bluetooth,
# audio topology + amp tuning).
set -euo pipefail
OUT=${1:?usage: collect_firmware.sh OUT_DIR}
adb shell "su -c id" | grep -q "uid=0" || { echo "need HyperOS with adb + root (Magisk)"; exit 1; }
G=$OUT/qcom/sm8650/xiaoxin/gt; mkdir -p "$G" "$OUT/novatek"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# ADSP/CDSP split images + protection-domain json from the modem partition (mounted by vendor)
adb exec-out "su -c 'cd /vendor/firmware_mnt/image && tar cf - adsp* cdsp* *.jsn'" > "$T/image.tar"
tar xf "$T/image.tar" -C "$G"
for f in adsp.mdt cdsp.mdt adsp_dtb.mdt cdsp_dtb.mdt battmgr.jsn adspr.jsn adsps.jsn adspua.jsn cdspr.jsn; do
  [ -s "$G/$f" ] || { echo "missing $f in /vendor/firmware_mnt/image"; exit 1; }
done
# GPU zap shader (signed for this device) and the touch controller firmware
adb exec-out "su -c 'cat /vendor/firmware/gen70900_zap.mbn'" > "$G/gen70900_zap.mbn"
adb exec-out "su -c 'cat /vendor/firmware/novatek_ts_fw.bin'" > "$OUT/novatek/novatek_nt36532_fw.bin"
[ -s "$G/gen70900_zap.mbn" ] && [ -s "$OUT/novatek/novatek_nt36532_fw.bin" ] || { echo "zap/touch firmware missing"; exit 1; }
echo "device firmware in $OUT:"; (cd "$OUT" && find . -type f | sort | sed 's/^/  /' | head -80)
