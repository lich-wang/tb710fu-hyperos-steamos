# 双系统开机菜单（kShimC）

## 结构

```
boot_a（100663296 字节分区，boot v4 头，page 4096）
 ├─ 头部：原 boot 的头（cmdline 加了 kShimC 回填诊断信息用的占位参数）
 ├─ kernel = PackedKernel（DualBootKernelPatcher 打包）
 │    ├─ kShimC 运行时（菜单、按键、屏幕、交接）
 │    ├─ Image-00 "HyperOS"  原 GKI 6.1 Image（BaseImage）
 │    ├─ Image-01 "SteamOS"  Linux 7.2.6-tb710fu Image（raw，不压缩）
 │    └─ Image-02            SteamOS 的 DTB
 └─ AVB hash footer：testkey_rsa4096，salt / 回滚索引 / 属性沿用原 boot
```

- 不碰 B 槽，不改 vbmeta：原 vbmeta 链式验证 boot，只要 footer 用同一测试密钥签名就能通过。
- ABL 能接受 86.5 MB 的 raw 打包内核。Linux 内核用精简配置，约 49 MB；完整发行版配置（65 MB）装不下。
- 菜单：音量键移动，电源键确认，8 秒后启动默认项。每个镜像的默认项在打包时决定。

## 构建 kShimC

源码组合（与 armadaos-freedom 当时使用的一致）：freedom 的 `kshim-success-source`、CrDK `b6c3335`、
picolibc `f7edb08`、lvgl `7f07a12`、kShimC 的 `lib/libfdt`（`libfdt_env.h` 需要补 `#include <stdlib.h>`）。

```
docker build -t kshim-build docker/kshim-build
# work/kshim-build/kshim = 上述源码；然后：
patch -d work/kshim-build/kshim -p1 < kshim/0001-tb710fu-sm8650-splash-mmu-reboot.patch
cp kshim/tb710fu_defconfig work/kshim-build/kshim/configs/
docker run --rm -v "$PWD/work/kshim-build":/w -v "$PWD/kshim":/s:ro kshim-build sh /s/build.sh menu
# -> work/kshim-build/out/menu/kShimC.bin
```

打包器 DualBootKernelPatcher（`2276163` + freedom 的 `patches/boot` 0001/0002 + inih）在同一容器里用 cmake 编译，
放到 `work/kshim-build/DBKP/build/`。`tools/kshim_pack_boot.py` 会自动找到其中的 `MultiBootKernelPatcher`。

## TB710FU 补丁（`kshim/0001-…patch`）说明

| 问题 | 处理 |
|---|---|
| 读不到 ABL 的开机画面（kShimC 要接管 framebuffer） | SM8650 的 ABL 用 **4 个 VIG 管线**（每个 800×2000，src_x 0/800/1600/2400，同一基址 `0xd5100000`）+ 4 个 LM 拼出 3200×2000 ARGB8888；原代码只支持 ≤2 路。新增 `tb710fu_splash_read`（按 `qcom,pineapple` 启用，校验各管线拼成连续缓冲且两次读取一致） |
| 开机多花 17 秒（DT 解析 6.9 s + 资源初始化 12.5 s） | kShimC 在关 MMU/缓存的状态下解析 3.2 MB 的 DT。入口处开临时 MMU（只把 kShimC 镜像和 FDT 设为 WB，其余 <64 GiB 为 Device，语义与关 MMU 相同），资源初始化后 clean+invalidate 两遍再关 → 61 ms + 100 ms |
| 菜单极卡 | DT 里 size=0 的保留节点（如 `mpss_dsm_region`）让菜单的 MMU 配置失败、全程无缓存 → `dt_reservations` 跳过 size=0 |
| Linux 启动时读到改写前的 FDT | 交接前对所有 WB 区（包括只读 FDT）做 clean+invalidate |
| 按键 | pmk8350 pwrkey/resin + PM8550 GPIO6（音量+）；按键解析放到菜单 MMU 开启之后 |
| 菜单里的重启到 Recovery/Fastboot/9008 | `qcom_reboot` 白名单加 `qcom,pineapple`（尚未逐项实测） |

调试技巧：`kshim_pack_boot.py --probe-slots` 会在 cmdline 里预留 `androidboot.kshim_s1..8` 等 80 字节占位参数，
kShimC 把诊断结果原地写进去，Android 起来后 `getprop ro.boot.kshim_*` 即可读到，不需要串口。

## 打包两个变体

```
STOCK_BOOT=work/stock/boot_a.img VBMETA=work/stock/vbmeta_a.img SHIM=work/kshim-build/out/menu/kShimC.bin \
  tools/kshim_variants.sh s1 out/Image out/sm8650-lenovo-tb710fu-kshim.dtb
# -> work/boot/current/boot_android.img（默认 HyperOS）、boot_linux.img（默认 SteamOS）
```

`STOCK_BOOT` 是你设备上能正常启动 HyperOS 的 boot_a（原 GKI 内核从这里取，footer 参数也从这里复制）。
脚本会用 `avbtool verify_image --follow_chain_partitions` 对照你自己的 vbmeta_a 验证，不通过就不输出。
DBKP 打包器偶尔会以 234 退出，脚本已自动重试。

## 写入与切换

- 第一次：HyperOS 下 root（Magisk）`dd` 写 `/dev/block/by-name/boot_a`，读回比对 sha256 后重启。
  务必先备份原 boot_a——它就是 `STOCK_BOOT`，也是回退手段。
- 之后用 `tools/mac/tbboot android|linux`：自动判断当前系统（HyperOS 走 adb+su，SteamOS 走 ssh+sudo），
  把默认项为目标系统的镜像写入 boot_a、读回校验、重启，不用手动选菜单。
- 开机时间：HyperOS 从上电到 adb 约 27 s（原版 16 s + 8 s 倒计时 + 约 3 s 菜单初始化）。
