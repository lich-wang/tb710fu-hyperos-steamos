#!/bin/bash
# flash_super.sh SUPER_IMG [--wipe]
# Write a HyperOS super image over EDL (tablet in 9008 mode: `adb reboot edl`).
#   --wipe   also zero the head of metadata and userdata (first boot = factory reset;
#            needed when the system/vendor combination changes)
# Optional: VENDOR_BOOT=... VBMETA_IMG=... also write vendor_boot_a / vbmeta_a.
# Env: EDL (bkerler/edl, default "edl"), LOADER (firehose programmer for TB710FU,
#      default work/firehose/prog_firehose_ddr-TB710FU.melf)
# Never touches persist/modemst*/fsg/fsc/devinfo/frp/keystore/ssd/secdata/... .
set -u
IMG=${1:?usage: flash_super.sh SUPER_IMG [--wipe]}; WIPE=${2:-}
EDL=${EDL:-edl}; LOADER=${LOADER:-work/firehose/prog_firehose_ddr-TB710FU.melf}
L=(--loader="$LOADER" --memory=ufs)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
step() { echo "$(date +%H:%M:%S) == $*"; }

step "check connection"
"$EDL" printgpt --lun=0 "${L[@]}" 2>&1 | grep -E "^super:" || { echo "EDL connection failed"; exit 1; }
step "write super $IMG ($(du -h "$IMG" | cut -f1))"
"$EDL" w super "$IMG" "${L[@]}" 2>&1 | grep -E "Wrote|rror|ail" || exit 1
if [ "$WIPE" = --wipe ]; then
  dd if=/dev/zero of="$T/zeros.bin" bs=1048576 count=64 2>/dev/null
  step "wipe metadata";    "$EDL" w metadata "$T/zeros.bin" "${L[@]}" 2>&1 | grep -E "Wrote|rror|ail"
  step "wipe userdata head"; "$EDL" w userdata "$T/zeros.bin" "${L[@]}" 2>&1 | grep -E "Wrote|rror|ail"
fi
if [ -n "${VENDOR_BOOT:-}" ] && [ -n "${VBMETA_IMG:-}" ]; then
  step "write vendor_boot_a + vbmeta_a"
  "$EDL" w vendor_boot_a "$VENDOR_BOOT" "${L[@]}" 2>&1 | grep -E "Wrote|rror|ail"
  "$EDL" w vbmeta_a "$VBMETA_IMG" "${L[@]}" 2>&1 | grep -E "Wrote|rror|ail"
fi
step "verify super head (lp metadata)"
# super starts at LUN0 sector 9608 (4 KiB sectors) in the stock TB710FU GPT
"$EDL" rs 9608 256 "$T/head.bin" --lun=0 "${L[@]}" >/dev/null 2>&1
cmp "$T/head.bin" <(head -c 1048576 "$IMG") && echo "SUPER METADATA OK" || echo "SUPER METADATA MISMATCH"
step "reset"
"$EDL" reset --resetmode=reset "${L[@]}" 2>&1 | tail -1
step "DONE"
