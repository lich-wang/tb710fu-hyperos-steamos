#!/bin/bash
# prepare_nbd_image.sh  - run inside a privileged arm64 Debian container:
#   docker run --rm --privileged -v "$PWD":/repo -v "$PWD/work":/work debian:trixie \
#       bash /repo/steamos/prepare_nbd_image.sh
# Inputs in /work:
#   steamos/steamos-arm-port-sm8650-v1.4.img   (7z x steamos-arm-port-sm8650-v1.4.7z.001)
#   kernel/modules-7.2.6-tb710fu.tar           (kernel/build.sh)
#   firmware/                                  (tools/collect_firmware.sh + docs/firmware.md)
#   ssh.pub                                    (your public key)
# Output: /work/steamos/steamos-tb710fu.img, served to the tablet by docker/nbd-server.
set -euo pipefail
apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  e2fsprogs util-linux kmod systemd patch fdisk >/dev/null
S=/work/steamos; IMG=$S/steamos-tb710fu.img
cp --sparse=always $S/steamos-arm-port-sm8650-v1.4.img $IMG
L=$(losetup -fP --show $IMG); trap 'umount -R /mnt/r 2>/dev/null || true; losetup -d $L' EXIT
mkdir -p /mnt/r; mount ${L}p2 /mnt/r; mount ${L}p3 /mnt/r/home
ROOT=/mnt/r SSH_PUBKEY=/work/ssh.pub bash /repo/steamos/install_payload.sh /work/kernel/modules-7.2.6-tb710fu.tar /work/firmware
df -h /mnt/r /mnt/r/home | tail -2
