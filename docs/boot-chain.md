# 启动链：锁 BL 下为什么能刷、怎么刷、怎么救

## 设备

- 联想小新平板 Pro GT，型号 **TB710FU**，骁龙 8 Gen 3（SM8650 / pineapple），UFS（LUN 0–5，4 KiB 扇区），256 GB。
- 原厂系统 ZUI 17.5（CN）。**ZUI 1.5.04.496 起无法解锁 Bootloader**；本项目全程在锁定状态下完成。
- 按键都在 PMIC 上：电源键（pwrkey）、音量下（resin）、音量上（PM8550 GPIO6）。

## 为什么锁 BL 也能启动改过的镜像

1. 这台机器的 ABL 验证 vbmeta 时信任 **AOSP 公开测试密钥**：`vbmeta`/`boot` 用 `testkey_rsa4096`、
   `vbmeta_system` 用 `testkey_rsa2048` 签名的镜像都能通过（`verifiedbootstate=green`、`locked`）。
   社区的"免解锁（WITHOUT_UBL）补充包"就是利用这一点。
2. 因此可以修改 `boot`、`vendor_boot`、`init_boot`、`dtbo` 等，只要：
   - 给改过的分区重新加 AVB hash footer（同一测试密钥），并让 `vbmeta` 里的摘要与之匹配；
   - **防回滚索引不能低于设备 RPMB 里记录的值**。实测 ZUI 495 的 `vbmeta_system` 回滚索引是 `1783209600`，
     `boot`（location 3）是 `1736035200`，其余为 0。降级到更低索引的镜像会直接拒绝启动。
3. 双系统的 boot 镜像沿用原 boot 的 salt、回滚索引和属性，只替换内容并重签 footer，所以**不需要改 vbmeta**。

工具：AOSP `avbtool`（`info_image` / `add_hash_footer` / `verify_image --follow_chain_partitions`）、
AOSP `mkbootimg` / `unpack_bootimg`。仓库不附带它们，放到 `tools/avb/`、`tools/mkbootimg/` 即可。

## 9008（EDL）

- 进入：`adb reboot edl`（需 root 或在 Android 下），或者拔线 → 长按电源 15–20 s 关机 → 按住音量+和音量−插线。
- 工具：[bkerler/edl](https://github.com/bkerler/edl) + 该机型的 firehose programmer（刷机包 `bin/9008/prog_firehose_ddr-TB710FU.melf`）。
  ```
  edl printgpt --lun=0 --loader=prog_firehose_ddr-TB710FU.melf --memory=ufs
  edl r boot_a boot_a.img --loader=... --memory=ufs
  ```
- **先备份**：所有 LUN 的 GPT、`persist`、`modemst1/2`、`fsg`、`fsc`、`devinfo`、`frp`、`keystore`、`ssd`、
  `secdata`、`uefivarstore`、`cdt`、`ddr`，以及 A 槽的 `abl boot init_boot vendor_boot dtbo vbmeta vbmeta_system recovery pvmfw`。
  唯一数据分区丢了没有任何地方能找回（IMEI、校准数据、密钥）。

## 900E：内核崩溃转储模式

设备 USB 枚举为 `05C6:900E`（Qualcomm HS-USB Diagnostics）时，说明内核 panic 后进入了 Sahara 内存转储。
`edl` 连上会识别出来并导出转储；在 `md_KBOOT_LOG.BIN` / `md_KLOGBUF.BIN` 里 `strings` 找 panic 前的日志，
就能看到真正的崩溃原因。调试时可以给 `vendor_boot` 的 bootconfig 加 `androidboot.init_fatal_panic=true`，
让 init 的致命错误也进 900E，便于抓日志。

## 本机的救砖与"v3 启动链"

起点：HyperOS 3 移植包（酷安 @兰微卡鱼，底包为红米平板 2 Pro）刷完后进 900E，转储显示：

```
init: [libfs_mgr] Invalid ext4 superblock on '/dev/block/dm-2'
init: Failed to mount /system: File exists
Kernel panic - not syncing: Attempted to kill init!
```

原因：免解锁补充包为了过防回滚，把整套启动链换成了 ZUI 495 的镜像；但 495 的 `vendor_boot` 里
first-stage fstab 对 system/vendor/product 等逻辑分区**只写了 ext4**，而 HyperOS 的 super 全是 **EROFS**。
单纯在 fstab 里加 erofs 条目后不再 panic，但又卡开机动画——495 的 boot 内核（6.1.157）与 super 里
system_dlkm/vendor_dlkm 的模块（6.1.128）版本不一致。

最终可用的 **v3 启动链**：
- `boot`、`init_boot`、`dtbo`、`vendor_boot` 用移植作者原版（内核 6.1.128，与模块匹配；fstab 每个逻辑分区 ext4+erofs 两条）。
  原版 `vendor_boot` 的 footer 摘要是旧的：`erase_footer` 后重新 `add_hash_footer`。
- 新 `vbmeta`：`testkey_rsa4096`，flags=1，chain `boot`/`recovery`/`vbmeta_system`。
- `vbmeta_system`、`pvmfw`、`recovery` **保留设备上 495 的版本**，以满足防回滚。

其他注意点：
- `metadata` 分区被清零过时不是有效 f2fs，首次开机会自动格式化，属正常。
- 刷机包里 `misc.img` 带 BCB `bootonce-bootloader`（首次启动进 fastboot），按需处理。
