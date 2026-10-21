#!/bin/bash
# install_payload.sh MODULES_TAR FIRMWARE_DIR
# Install the TB710FU kernel modules, firmware and rootfs/ of this repository into SteamOS.
#   MODULES_TAR   modules-7.2.6-tb710fu.tar from kernel/build.sh
#   FIRMWARE_DIR  a tree laid out like /usr/lib/firmware with this device's firmware
#                 (see docs/firmware.md; none of it can be redistributed)
# Where:
#   on the tablet, in SteamOS, as root:   install_payload.sh ...
#   into a mounted image (offline):       ROOT=/mnt/root install_payload.sh ...  (arm64 host or container)
# SteamOS mounts an overlay on /etc only after systemd has loaded its units, so everything
# for /etc goes into the LOWER /etc (on a live system: a bind mount of /).
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
MOD=${1:?usage: install_payload.sh MODULES_TAR FIRMWARE_DIR}; FW=${2:?}
KV=7.2.6-tb710fu
ROOT=${ROOT:-/}
if [ "$ROOT" = / ]; then
  E=/run/tb710fu-lower; mkdir -p $E; mountpoint -q $E || mount --bind / $E; trap 'umount $E' EXIT
else
  E=$ROOT
fi

echo "== kernel modules"
rm -rf "$ROOT/usr/lib/modules/$KV"; tar xf "$MOD" -C "$ROOT/usr/lib/modules"; depmod -b "$ROOT" $KV
echo "== firmware"
cp -a --no-preserve=ownership "$FW"/. "$ROOT/usr/lib/firmware/"
echo "== rootfs"
cp -a --no-preserve=ownership "$REPO/steamos/rootfs/usr/." "$ROOT/usr/"
cp -a --no-preserve=ownership "$REPO/steamos/rootfs/etc/." "$E/etc/"
S=$E/etc/systemd/system; mkdir -p $S/multi-user.target.wants $S/display-manager.service.wants
for u in tb-native-display tb-usb-ncm tb-usb-ncm-watch tb-wifi tb-audio-init tb-adsp-audio-check tb-touch-check; do
  ln -sfn /etc/systemd/system/$u.service $S/multi-user.target.wants/$u.service
done
ln -sfn /etc/systemd/system/tb-native-display.service $S/display-manager.service.wants/tb-native-display.service
mkdir -p $E/etc/systemd/user/gamescope-session.target.wants
for u in tb-touch-auto tb-touch-gestures; do
  ln -sfn /etc/systemd/user/$u.service $E/etc/systemd/user/gamescope-session.target.wants/$u.service
done
echo "== pen hwdb"
systemd-hwdb update --usr --root="$ROOT"
echo "== gamescope touch mode"
G=$ROOT/usr/lib/steamos/gamescope-session
[ -f "$G.tb710fu-orig" ] || cp -p "$G" "$G.tb710fu-orig"
grep -q tb710fu/touch-mode "$G" || patch -N -p1 -d "$ROOT" < "$REPO/steamos/patches/gamescope-session-touch-mode.patch"
[ "$ROOT" = / ] && systemctl daemon-reload
sync
echo "done"
