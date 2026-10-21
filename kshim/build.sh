#!/bin/sh
# build.sh OUTNAME [cmake args...]  - run inside docker/kshim-build with /w = the work tree that
# holds kshim/ (kShimC source with our patch applied) and out/. Default profile: tb710fu_defconfig.
# Diagnostic menu build: build.sh menu_diag -DCMAKE_C_FLAGS=-DTB710FU_MENU_DIAG=1
set -e
git config --global --add safe.directory "*"
cd /w/kshim
out=/w/out/$1; shift; rm -rf $out; mkdir -p $out
cp configs/${KCONFIG:-tb710fu_defconfig} $out/.config
cmake -S . -B $out -G Ninja -DKSHIM_STANDALONE=OFF -DKSHIM_RUNTIME_SLOT_SIZE=0x400000 \
  -DKSHIM_UEFI_PAYLOAD= -DCMAKE_BUILD_TYPE=Release "$@" > $out/configure.log 2>&1 || { tail -30 $out/configure.log; exit 1; }
cmake --build $out -j8 > $out/build.log 2>&1 || { grep -E "error" $out/build.log | head -20; exit 1; }
grep -E "warning" $out/build.log | grep -E "splash.c|main.c" | head
ls -l $out/kShimC.bin; echo "undef: $(aarch64-linux-gnu-nm -u $out/kShimC.elf | wc -l)"
