#!/bin/bash
# TB710FU: move the running (NBD-root) SteamOS onto UFS. Run as root on the tablet.
#  1. GPT on /dev/sda (4K sectors): shrink sda14 userdata to 5105064..27836415 (86.7 GiB,
#     same name/type/unique GUID), add sda15 "steamos" 27836416..61390842 (128 GiB).
#  2. Wipe the heads of userdata and metadata -> HyperOS formats both on its next boot
#     (factory-reset state). BACK UP userdata/metadata FIRST if you need anything on them.
#  Sector numbers are for the 256 GB model (sda14 userdata = 5105064..61390842); check yours.
#  3. ext4 "steamos-root" on sda15, copy / and /home of the running system into it.
#  4. fstab: root by label, /home is a directory of root; USB NCM services for ssh.
set -euo pipefail
D=/dev/sda
[ "$(blockdev --getss $D)" = 4096 ] || { echo "unexpected sector size"; exit 1; }
sgdisk -i 14 $D | grep -q "Partition name: 'userdata'" || { echo "sda14 is not userdata"; exit 1; }
sgdisk -i 14 $D | grep -q "Last sector: 61390842" || { echo "sda14 already changed?"; exit 1; }
G=$(sgdisk -i 14 $D | sed -n 's/^Partition unique GUID: //p')   # keep userdata's own GUID
[ -n "$G" ] || { echo "cannot read userdata GUID"; exit 1; }
for p in 11 14; do ! grep -q "^/dev/sda$p " /proc/mounts || { echo "sda$p mounted"; exit 1; }; done
sgdisk -d 14 \
  -n 14:5105064:27836415 -c 14:userdata -t 14:1B81E7E6-F50D-419B-A739-2AEEF8DA3335 -u 14:$G \
  -n 15:27836416:61390842 -c 15:steamos -t 15:8300 $D
sgdisk -v $D | tail -2
partx -u $D || partprobe $D || true
sleep 2
[ -b /dev/sda15 ] || { echo "no sda15 after reread"; exit 1; }
sgdisk -i 14 $D | grep -E "name|First|Last|unique"; sgdisk -i 15 $D | grep -E "name|First|Last"
dd if=/dev/zero of=/dev/sda14 bs=1M count=64 conv=fsync status=none
dd if=/dev/zero of=/dev/sda11 bs=1M conv=fsync status=none || true   # metadata (64 MiB)
mkfs.ext4 -q -F -L steamos-root /dev/sda15
mkdir -p /mnt/steamos; mount -o noatime /dev/sda15 /mnt/steamos
rsync -aHAXx --numeric-ids --info=stats1 / /mnt/steamos/
# /etc is an overlay mount on SteamOS (lower = root's /etc, upper = /var/lib/overlays/etc/upper):
# -x skips it, so copy the lower /etc from a bind mount of /
mkdir -p /mnt/rootbind; mount --bind / /mnt/rootbind
rsync -aHAX --numeric-ids /mnt/rootbind/etc/ /mnt/steamos/etc/; umount /mnt/rootbind
rsync -aHAXx --numeric-ids --info=stats1 /home/ /mnt/steamos/home/
mkdir -p /mnt/steamos/{proc,sys,dev,run,tmp,boot,mnt}
F=/mnt/steamos/etc/fstab
sed -i -E 's|^UUID=[0-9a-f-]+[[:space:]]+/[[:space:]]+ext4|LABEL=steamos-root  /  ext4|; /[[:space:]]\/home[[:space:]]/d' $F
# the overlay upper has its own fstab copy that wins over the lower one: fix both
U=/mnt/steamos/var/lib/overlays/etc/upper/fstab
[ -f $U ] && sed -i -E 's|^[^#[:space:]]+[[:space:]]+/[[:space:]]+ext4|LABEL=steamos-root  /  ext4|; /[[:space:]]\/home[[:space:]]/d' $U
cat $F
# /home is a directory of root now: the stock home.mount (by-partsets/shared/home) would
# block every login session (sddm autologin, ssh) on a device timeout -> mask it, and the
# SM8550 home-expander. systemd loads units before the /etc overlay is mounted, so masks
# (and every unit of ours) must live in the LOWER /etc, i.e. /mnt/steamos/etc here.
mkdir -p /mnt/steamos/etc/systemd/system/multi-user.target.wants
ln -sf /dev/null /mnt/steamos/etc/systemd/system/home.mount
ln -sf /dev/null /mnt/steamos/etc/systemd/system/steamos-sm8550-expand-home.service
install -m755 /tmp/tb-usb-ncm /tmp/tb-usb-ncm-watch /mnt/steamos/usr/local/sbin/
install -m644 /tmp/tb-usb-ncm.service /tmp/tb-usb-ncm-watch.service /mnt/steamos/etc/systemd/system/
ln -sf /etc/systemd/system/tb-usb-ncm.service /mnt/steamos/etc/systemd/system/multi-user.target.wants/
ln -sf /etc/systemd/system/tb-usb-ncm-watch.service /mnt/steamos/etc/systemd/system/multi-user.target.wants/
rm -f /mnt/steamos/etc/sudoers.d/90-tb710fu-test
sync; df -h /mnt/steamos; umount /mnt/steamos
echo INSTALL-OK
