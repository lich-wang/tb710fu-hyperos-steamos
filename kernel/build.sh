#!/bin/bash
# Build the 7.2.6-tb710fu kernel (Image + kshim DTB + modules) inside docker/kernel-build.
#
#   docker build -t kernel-build docker/kernel-build
#   git clone https://github.com/mydanyi/armadaos-freedom freedom && git -C freedom checkout ba692d8
#   docker run --rm -v "$PWD":/repo:ro -v "$PWD/freedom":/freedom:ro -v "$PWD/out":/out \
#              -v tb-kwork:/build kernel-build bash /repo/kernel/build.sh
#
# Output in /out: Image, sm8650-lenovo-tb710fu-kshim.dtb, modules-7.2.6-tb710fu.tar
# Kernel tree = linux 7.2.6 + armadaos-freedom kernel patches/dts ("freedom-base")
#             + tb710fu-kernel-on-freedom.patch (everything TB710FU-specific).
# Keep the tree on a docker volume: macOS bind mounts are case-insensitive.
set -euo pipefail
V=7.2.6
cd /build
[ -f linux-$V.tar.xz ] || curl -fLO https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-$V.tar.xz
rm -rf linux-$V; tar -xf linux-$V.tar.xz; cd linux-$V

FK=/freedom/packages/kernel
while IFS= read -r p; do
  p="${p%%#*}"; p="${p## }"; p="${p%% *}"; [ -z "$p" ] && continue
  # same rule as when the patch below was made: exact apply or skip
  patch -p1 --batch --forward -F0 --no-backup-if-mismatch --quiet < "$FK/patches/$p" >/dev/null 2>&1 || echo "freedom: skipped $p"
done < "$FK/patches/series"
cp "$FK"/dts/*.dts "$FK"/dts/*.dtsi arch/arm64/boot/dts/qcom/
for p in "$FK"/dts/*.patch; do patch -p1 -F0 --no-backup-if-mismatch -s < "$p" || echo "freedom dts: skipped $p"; done

patch -p1 --no-backup-if-mismatch < /repo/kernel/tb710fu-kernel-on-freedom.patch

# initramfs: static busybox + our init scripts
mkdir -p ../initramfs; cp /bin/busybox ../initramfs/busybox
cp /repo/kernel/initramfs/{init,diag.sh,nbdroot.sh} ../initramfs/
cat > initramfs.list <<LIST
dir /dev 755 0 0
nod /dev/console 600 0 0 c 5 1
dir /bin 755 0 0
dir /proc 755 0 0
dir /sys 755 0 0
dir /tmp 1777 0 0
dir /run 755 0 0
dir /newroot 755 0 0
file /bin/busybox $PWD/../initramfs/busybox 755 0 0
file /init $PWD/../initramfs/init 755 0 0
file /diag.sh $PWD/../initramfs/diag.sh 755 0 0
file /nbdroot.sh $PWD/../initramfs/nbdroot.sh 755 0 0
LIST

cp /repo/kernel/config-$V-tb710fu .config
make -s LOCALVERSION= olddefconfig
make -j"$(nproc)" LOCALVERSION= Image dtbs modules
rm -rf ../modstage; make -s LOCALVERSION= INSTALL_MOD_PATH=../modstage INSTALL_MOD_STRIP=1 modules_install
KV=$(make -s LOCALVERSION= kernelrelease)
rm -f ../modstage/lib/modules/$KV/{build,source}
tar cf /out/modules-$KV.tar -C ../modstage/lib/modules "$KV"
cp arch/arm64/boot/Image arch/arm64/boot/dts/qcom/sm8650-lenovo-tb710fu-kshim.dtb /out/
ls -l /out
