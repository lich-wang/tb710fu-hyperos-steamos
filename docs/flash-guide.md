# 刷机指南：从联想官方系统到 HyperOS 4 + SteamOS 双系统

> **建议让 AI Agent 带着你做**：把本仓库交给一个能执行命令的 AI 编程 Agent，让它先完整阅读
> [`AGENT.md`](../AGENT.md)（给 Agent 的操作规程）和本文，再一步步执行。Agent 每次写入设备前都会把要写的分区和命令列给你确认；
> 需要你动手的地方（进 9008、按电源键、在平板上点）它会停下来等你。

**状态标记**：✅ 已在本机实测的步骤；🔧 本机当时是手工完成的，这里给的是整理后的等价脚本，脚本本身未完整跑过一遍。

> ⚠️ 风险：会清空平板全部数据、改写分区表和启动链。设备唯一数据分区（persist、modemst1/2、fsg、fsc、devinfo、frp、keystore、
> ssd、secdata、uefivarstore、cdt、ddr）全程**不写**，但必须先备份。后果自负。

---

## 0. 前提

| 项目 | 要求 |
|---|---|
| 设备 | 联想小新 Pad Pro GT **TB710FU**，**256 GB**（分区扇区号按 256 GB 写的），国行 ZUI |
| 系统版本 | **ZUI 1.5.04.495**。495 以后（496 起）无法解锁 BL；本方案虽不解锁，但用到的启动链镜像回滚索引按 495 设计，更新版本的防回滚索引可能更高，镜像会被拒绝（推测，未验证）——**不是 495 就不要继续** |
| 电脑 | Apple Silicon Mac（`tools/build_os4.py` 用了 APFS 的 `cp -c`），Docker Desktop，Homebrew，约 200 GB 空闲空间 |
| 数据线 | USB-C，全程不能松动（尤其 9008 写入和 NBD 阶段） |

Mac 上的工具：

```bash
brew install android-platform-tools payload-dumper-go erofs-utils zstd p7zip python@3.12
python3 -m venv tools/venv && tools/venv/bin/pip install git+https://github.com/bkerler/edl
```

把 AOSP 的 `avbtool.py`（external/avb）和测试密钥 `testkey_rsa4096.pem`、`testkey_rsa2048.pem`（external/avb/test/data）放到 `tools/avb/`。

需要下载（都不在本仓库里，放到 `work/` 下）：

| 文件 | 来源 | 用途 |
|---|---|---|
| HyperOS 3.0.305 移植包 + `1.5.04.495_WITHOUT_UBL` 免解锁补充包 | 酷安 @兰微卡鱼 | 9008 线刷包（固件、GPT、HyperOS 3 super）、作者原版启动镜像 |
| 小米平板 8（yupei）`OS4.0.5.0.XPZCNXM` OTA 全量包 | 小米官方 | HyperOS 4 的 system/system_ext/product/mi_ext |
| SteamOS-ARM-Port v1.4 sm8650（`.7z.001~003`） | [GitHub releases](https://github.com/hashtagbasit/SteamOS-ARM-Port) | SteamOS 用户空间 |
| armadaos-freedom（`ba692d8`） | [GitHub](https://github.com/mydanyi/armadaos-freedom) | 内核补丁基线、kShimC 源码组合 |
| DualBootKernelPatcher（`2276163`）、kShimC 依赖 | 见 [dualboot-kshim.md](dualboot-kshim.md) | 双系统打包 |
| linux-firmware、tb710fu-linux 的 board-root | 见 [firmware.md](firmware.md) | GPU/WiFi/蓝牙/音频固件 |

## 1. 进入 9008 并完整备份 ✅

进 9008：关机拔线 → 长按电源 15–20 秒确保关机 → **按住音量+ 和音量−** 插线。Mac 上 `system_profiler SPUSBDataType` 能看到
`QUSB__BULK`（05C6:9008）。已 root 的 Android 下也可以 `adb reboot edl`。

```bash
L="--loader=work/HyperOS3.0.305/bin/9008/prog_firehose_ddr-TB710FU.melf --memory=ufs"
EDL=tools/venv/bin/edl
$EDL printgpt --lun=0 $L                                  # 能列出分区表 = 连接正常
$EDL gpt work/backup/gpt --genxml $L                      # 6 个 LUN 的 GPT
$EDL rl work/backup/parts --skip=userdata,super $L        # 其余所有分区（约 5 GB）
```

firehose 的 sha256 应为 `ad4689b1c52458250d46829ee46a89ec974e69f8e82eee8d4950427919e0b9eb`。
**确认 `work/backup/parts` 里有 persist、modemst1、modemst2、fsg、fsc、devinfo、frp、keystore、ssd、secdata、uefivarstore、cdt、ddr，
再备份一份到别处。** 这些丢了就再也找不回来（IMEI、射频校准、密钥）。

## 2. 线刷 HyperOS 3 移植包 ✅

移植包的 `rawprogram*.xml` 对唯一数据分区的 `filename` 都是空的，edl 会跳过，不会写入。它会写 GPT、各固件分区、misc 和 super。

```bash
cd work/HyperOS3.0.305/images
../../../tools/venv/bin/edl qfil rawprogram0.xml,rawprogram1.xml,rawprogram2.xml,rawprogram3.xml,rawprogram4.xml,rawprogram5.xml \
   patch0.xml,patch1.xml,patch2.xml,patch3.xml,patch4.xml,patch5.xml . $L
```

（Windows 上可以用包里的 `点我一键刷入.cmd` 选项 3"9008 深度线刷"。）刷完**先不要开机**，接着做第 3 步。
此时 A 槽是 495 的启动链，单独开机会进 900E（vendor_boot 的 fstab 只认 ext4，而 super 是 EROFS）。

## 3. 换成 v3 启动链 ✅

从移植包 zip（`HyperOS3.0.305_A16_TB710FU[c0f13e].zip`）里取出作者原版的 `boot.img`、`init_boot.img`、`dtbo.img`、`vendor_boot.img`
（内核 6.1.128，与 super 里的模块匹配），放到 `work/author/`：

```bash
tools/venv/bin/python tools/make_v3_bootchain.py work/author work/v3
shasum -a 256 work/v3/*.img
```

同一个移植包生成的结果应**逐字节等于**：

| 文件 | sha256 |
|---|---|
| boot.img | `e35390577fcbfa4a69d87323a54a501392229cff45b08b41ea7bf883439bd90d` |
| init_boot.img | `3ac931533d69156b50cb9a07683021ac53f78166d0a66ae9d77f4f54a7b3f703` |
| dtbo.img | `088063818de6dc7a9852a31a86d5ad7019bdc74157890b0506a0bc3677390f27` |
| vendor_boot.img | `988b8aa16c9a6174f8fd349f72901849ce59e643a304401bf1561c51a74b1224` |
| vbmeta.img | `b641de6c2c42d2fa2b0a3a1d50be913fa4bea2d0988e4a95aecf1e528ba3057c` |

```bash
for p in boot init_boot dtbo vendor_boot vbmeta; do $EDL w ${p}_a work/v3/$p.img $L; done
$EDL reset --resetmode=reset $L
```

`vbmeta_system_a`、`pvmfw_a`、`recovery_a` 保持移植包（= 495 补充包）里的版本，不要动——它们带着设备已记录的防回滚索引。
包里的 misc 带 `bootonce-bootloader`，首次可能停在 fastboot，`fastboot reboot` 即可。

**检查点**：能进 HyperOS 3 开机向导。完成向导（可以不登录小米账号），开发者选项里打开 USB 调试。

## 4. Magisk root（HyperOS 3）✅

后面要从 HyperOS 里取固件、切换系统，需要 root。安装 Magisk app → 修补 `work/v3/init_boot.img` → 取回修补后的文件，
放到一个新目录（连同 boot/dtbo/vendor_boot 原样）重新生成 vbmeta（init_boot 的摘要在 vbmeta 里）：

```bash
mkdir -p work/v3root && cp work/author/{boot,dtbo,vendor_boot}.img work/v3root/ && cp magisk_patched.img work/v3root/init_boot.img
tools/venv/bin/python tools/make_v3_bootchain.py work/v3root work/v3root/out
adb reboot edl
$EDL w init_boot_a work/v3root/out/init_boot.img $L && $EDL w vbmeta_a work/v3root/out/vbmeta.img $L && $EDL reset --resetmode=reset $L
```

**检查点**：`adb shell su -c id` 返回 `uid=0`（在 Magisk 里允许 Shell）。

## 5. 收集本机固件 🔧

```bash
tools/collect_firmware.sh work/firmware          # ADSP/CDSP、battmgr、GPU zap、触摸固件
```

再按 [firmware.md](firmware.md) 补上 linux-firmware / tb710fu-linux 的文件；拓扑文件用 `tools/patch_tplg.py` 改成 TDM：

```bash
python3 tools/patch_tplg.py board-root/.../Lenovo-TB710FU-tplg.bin work/firmware/qcom/sm8650/Lenovo-TB710FU-tplg.bin
```

## 6. 编译内核 ✅

先把 `kernel/tb710fu-kernel-on-freedom.patch` 里 kshim DTS 的 `local-bd-address = [00 00 00 00 00 00]` 改成你这台的蓝牙地址
（`adb shell getprop ro.odm.lenovo.btaddr`，**倒序**写入；不改也能用，地址会按序列号生成）。

```bash
docker build -t kernel-build docker/kernel-build
git clone https://github.com/mydanyi/armadaos-freedom work/freedom && git -C work/freedom checkout ba692d8
docker run --rm -v "$PWD":/repo:ro -v "$PWD/work/freedom":/freedom:ro -v "$PWD/work/kernel":/out \
           -v tb-kwork:/build kernel-build bash /repo/kernel/build.sh
```

**检查点**：`work/kernel/` 下有 `Image`（约 49 MB）、`sm8650-lenovo-tb710fu-kshim.dtb`、`modules-7.2.6-tb710fu.tar`。

## 7. 双系统开机菜单 ✅

按 [dualboot-kshim.md](dualboot-kshim.md) 编译 kShimC（`work/kshim-build/out/menu/kShimC.bin`）和 DualBootKernelPatcher，然后：

```bash
adb shell "su -c 'dd if=/dev/block/by-name/vbmeta_a'" > work/stock/vbmeta_a.img     # 用设备上当前的 vbmeta
cp work/v3/boot.img work/stock/boot_a.img                                           # 原 GKI 内核从这里取
SHIM=work/kshim-build/out/menu/kShimC.bin tools/kshim_variants.sh v1 work/kernel/Image work/kernel/sm8650-lenovo-tb710fu-kshim.dtb
adb reboot edl
$EDL w boot_a work/boot/current/boot_android.img $L && $EDL reset --resetmode=reset $L
```

**检查点**：开机出现菜单（HyperOS / SteamOS），音量键移动，8 秒后进 HyperOS，HyperOS 正常。
回退：`$EDL w boot_a work/v3/boot.img $L`。

## 8. SteamOS 先用网络根盘试跑 ✅（脚本 🔧）

```bash
7z x work/steamos/steamos-arm-port-sm8650-v1.4.7z.001 -owork/steamos
cp ~/.ssh/id_ed25519.pub work/ssh.pub
docker run --rm --privileged -v "$PWD":/repo -v "$PWD/work":/work debian:trixie bash /repo/steamos/prepare_nbd_image.sh
docker build -t tb-nbd docker/nbd-server
docker run -d --name tb-nbd-server -p 10809:10809 -v "$PWD/work/steamos":/img \
   -v "$PWD/docker/nbd-server/nbd.conf":/etc/nbd-server/config:ro tb-nbd \
   sh -c 'nbd-server -C /etc/nbd-server/config; exec sleep infinity'
caffeinate -dims &                                   # 试跑期间 Mac 不能睡眠
```

平板开机菜单选 **SteamOS**：设备上没有名为 `steamos` 的分区，initramfs 会建 USB 网络，从 Mac 的 10809 端口挂载根盘。
**检查点**：屏幕进入 Steam；Mac 上出现 172.16.42.x 的网卡；`ssh root@172.16.42.1` 能登录。

## 9. 把 SteamOS 装进 UFS ✅

> ⚠️ 这一步**清空 HyperOS 的数据**（userdata 缩小并清零）。

```bash
scp steamos/steamos_install_ufs.sh root@172.16.42.1:/tmp/ && ssh root@172.16.42.1 bash /tmp/steamos_install_ufs.sh
```

脚本会检查扇区大小和 userdata 的位置，然后把 userdata 缩到 86.7 GiB、新建 128 GiB 的 `steamos` 分区，格式化并复制当前系统，
最后打印 `INSTALL-OK`。之后停掉 NBD 服务（`docker rm -f tb-nbd-server`），重启平板选 SteamOS。
**检查点**：拔掉数据线也能进 SteamOS；`df /` 显示 `/dev/sda15`。

## 10. 刷入 HyperOS 4 ✅（输入准备 🔧）

准备输入（全部在 `work/` 下，详见 [hyperos4.md](hyperos4.md)）：

```bash
Y=work/hyperos4_yupei; mkdir -p $Y/img
payload-dumper-go -p system,system_ext,product,mi_ext -o $Y/img work/yupei-ota_full-OS4.0.5.0.XPZCNXM-*.zip
for p in system system_ext product mi_ext; do fsck.erofs --extract=$Y/x_$p $Y/img/$p.img; done
zstd -d work/HyperOS3.0.305.0/super.img.zst -o work/port/super.img     # 移植包里的 super
python3 tools/lp_unpack.py work/port/super.img work/port system_a system_ext_a product_a vendor_a odm_a vendor_dlkm_a system_dlkm_a
for p in system product; do fsck.erofs --extract=work/port/x_${p}_a work/port/${p}_a.img; done
```

`work/port/` 里 vendor/odm/dlkm 的 sha256 应为：vendor_a `f4a36740…`、odm_a `7d54d8a1…`、vendor_dlkm_a `82c36224…`、system_dlkm_a `a99b741b…`。

USB 网络共享需要的两个 overlay 用 apktool 从 `hyperos/overlay/` 构建、用你自己的密钥签名，放到 `work/overlay/`。然后：

```bash
TB_NO_FINDDEVICE=1 python3 tools/build_os4.py && mv work/build_os4/out/product.img work/build_os4/out/product_nofind.img
python3 tools/build_os4.py
O=work/build_os4/out; V="vendor=work/port/vendor_a.img odm=work/port/odm_a.img vendor_dlkm=work/port/vendor_dlkm_a.img system_dlkm=work/port/system_dlkm_a.img"
python3 tools/make_super.py $O/super_nofind.img 0x4c0000000 system=$O/system.img system_ext=$O/system_ext.img product=$O/product_nofind.img $V
python3 tools/make_super.py $O/super_find.img   0x4c0000000 system=$O/system.img system_ext=$O/system_ext.img product=$O/product.img $V
adb reboot edl          # 或在 SteamOS 下用 tbboot 回到 HyperOS 再 adb reboot edl / 按键进 9008
export EDL=tools/venv/bin/edl LOADER=work/HyperOS3.0.305/bin/9008/prog_firehose_ddr-TB710FU.melf
tools/flash_super.sh $O/super_nofind.img --wipe
```

1. 开机进 HyperOS 4 开机向导，**向导里不要登录小米账号**（否则会卡在 `cloudsp_fid 参数不能为空` 的激活锁）。
2. 向导完成后进 9008：`tools/flash_super.sh $O/super_find.img`（不加 `--wipe`，数据保留）。
3. 在"设置"里登录小米账号。**永远不要打开"查找设备"**。
4. USB 网络共享：`adb shell settings put global tether_force_usb_functions 1`，再在设置里打开。

## 11. 日常使用

- 切换系统：`tools/mac/tbboot android|linux`（HyperOS 下通过 adb+root，SteamOS 下通过 ssh）。
- SteamOS 的触摸手势、笔、睡眠等见 [steamos.md](steamos.md)；Linux 原生游戏出问题时强制 Proton 11.0 (ARM64)。
- 想要一个能整机恢复的备份：在 HyperOS 下用 root 只读导出所有分区（userdata 除外），SteamOS 做成干净的系统镜像，
  再生成 rawprogram XML。注意 HyperOS 的 userdata **不能**原始备份/恢复（TEE 防回滚，见 [lessons.md](lessons.md)）。

## 出问题时

| 现象 | 处理 |
|---|---|
| USB 显示 `05C6:900E` | 内核崩溃转储。`edl` 连上会导出转储，在 `md_KBOOT_LOG.BIN` 里找 panic 原因（见 [boot-chain.md](boot-chain.md)） |
| 开机菜单后黑屏 / 进不了系统 | 进 9008 写回 `work/v3/boot.img` 到 boot_a，先恢复 HyperOS |
| HyperOS 卡开机动画 | 用 `TB_DEBUG=1` 构建调试版 super，开机 adb 可用，看 logcat（见 [hyperos4.md](hyperos4.md) 排错记录） |
| PIN 解不开 / Gatekeeper -30 | 写过旧的 userdata 镜像导致，只能清数据重走向导 |
| SteamOS 黑屏、Steam 不停重启 | 多半是音频配置被覆盖，见 [steamos.md](steamos.md#音频) |
