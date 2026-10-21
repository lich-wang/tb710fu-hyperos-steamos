# HyperOS 4 移植

## 思路

- **启动链不动**：沿用 [boot-chain.md](boot-chain.md) 的 v3 启动链（作者原版 boot/vendor_boot，内核 6.1.128）。
- **vendor 侧不动**：`vendor`、`odm`、`vendor_dlkm`、`system_dlkm` 用 HyperOS 3 移植包的（Android 14 vendor 接口）。
- **只换框架侧**：`system`、`system_ext`、`product`（`mi_ext` 合并进 `product`）换成 HyperOS 4。
- 失败时把原来的 super 写回即可恢复。

## 底包选择

| 候选 | 结论 |
|---|---|
| 小米平板 8 Pro（piano）OS4 Beta | ✗ XRING 芯片 + 16K 页内核，不适合 |
| 红米平板 2 Pro（flute） | HyperOS 3 移植包的真正底包（只是改名 piano）；OS4 推送前不可用 |
| **小米平板 8（yupei，骁龙 8s Gen 4）OS4.0.5.0.XPZCNXM 稳定版** | ✓ 4K 页设备；采用 |

离线兼容性检查（刷机前）：vendor 的 39 个 `android.hardware` HAL 全部被新框架的 FCM 接受；
SELinux `34.0.cil` 映射存在；VNDK v34 apex 在；system_ext 的 VINTF 只多了 2 个可选服务。
四个分区合计约 8.6 GB，加 vendor/odm 等约 10.6 GB，小于 super 物理大小 20.4 GB（GPT 长度 `0x4c0000000`）。

## 改动清单（`tools/build_os4.py` 自动完成）

`build_os4.py` 读出原镜像的 EROFS 元数据（uid/gid/mode、`security.selinux`/`security.capability` xattr、符号链接，
见 `tools/erofs_meta.py`），在 staging 目录修改后打 PAX tar（xattr 原样字节写入），再用
`mkfs.erofs -zlz4hc,9 -b4096 --tar=f` 生成镜像——所有文件的属主、权限和 SELinux 标签与原镜像逐项一致。

- **product build.prop**：`ro.product.cpu.pagesize.max=4096`、删除 `ro.product.build.no_bionic_page_size_macro`
  和 `ro.sf.lcd_density`；合入 mi_ext 的属性（`mod_device=piano`）；移植作者的 `lwky.hyper.*` 机型伪装、
  `persist.sys.stylus.enable=1`、电池/充电属性、关闭 LE Audio；`debug.hwui.renderer=skiagl`（见下文无线副屏）；
  `ro.build.version.incremental` 末尾加 `.DEV`（见下文小米账号）。
- **system build.prop**：注释掉 `media.settings.xml=/vendor/etc/media_profiles_vendor.xml`（本 vendor 没有该文件）。
- **移植作者的系统改动**：`system/etc/init/init.lwky.rc` + `system/lwky/*`（分辨率、窗口规则、智能充电）、
  Joyose、权限 xml；pangu 内容并入 system（去掉 NFC 的 `com.tms.*` jar）。
- **`device_features/piano.xml`** = yupei 的 features，其中 `support_tee_face_unlock=false`。
- **SELinux**：`hyperos/sepolicy_compat.cil` 追加到 `product_sepolicy.cil`（见排错 3）。
- **笔按键**：`system/usr/keylayout/Vendor_17ef_Product_617f.kl`（`hyperos/keylayout/`）。
- **USB 网络共享（NCM）**：两个 RRO（`hyperos/overlay/`，自己签名后放到 `work/overlay/`）。
- **人脸解锁**：HyperOS 3 的 PearlBiometric（`com.miui.face`，非 TEE 方案）放进 product。

`tools/make_super.py` 生成 super：liblp 元数据 v10.2、VAB 标志、3 个槽位元数据、1 MiB 对齐、设备大小 `0x4c0000000`。

```
python3 tools/build_os4.py            # 产出 work/build_os4/out/{system,system_ext,product}.img
python3 tools/make_super.py work/build_os4/out/super.img 0x4c0000000 \
    system=... system_ext=... product=... vendor=... odm=... vendor_dlkm=... system_dlkm=...
tools/flash_super.sh work/build_os4/out/super.img --wipe     # 9008 下
```

环境变量：`TB_DEBUG=1` 构建调试版（`ro.debuggable=1`、adb 免授权并在开机早期就可用，便于抓 logcat）；
`TB_NO_FINDDEVICE=1` 去掉查找设备（见下文）。

## 排错记录（按出现顺序）

1. **刷入即 900E**：`erofs: blkszbits 14 isn't supported`——macOS 上 `mkfs.erofs` 默认按 16K 页建块。加 `-b4096`。
2. **8 秒回到 fastboot**：用户版不写 UEFI 日志，`misc` 里也没有 BCB。换调试 `vendor_boot`
   （`androidboot.init_fatal_panic=true`）后从 900E 转储看到 init 死在 "Compiling SELinux policy"。
3. **SELinux 编译失败**：vendor 策略引用了 5 个 Android 17 已删除的类型
   （`bluetooth_lea_mode_prop`、`persist_sysui_builder_extras_prop`、`persist_sysui_ranking_update_prop`、
   `wae_prop`、`vendor_wifibtmac_prop`）。`tools/sepolicy_fix.py` 用 secilc 按 init 的顺序离线编译，
   缺什么就从旧策略里把声明补进 `sepolicy_compat.cil`，直到编译通过。
4. **开机动画转圈**：调试版 logcat 显示 zygote 每 5 秒 SIGABRT（`MediaProfiles::createInstanceFromXmlFile` 断言）
   → 上面那条 `media.settings.xml`。
5. **首次开机 adb 被关**：小米框架在开机向导时会把 USB 切回 MTP。调试版额外放一个 init rc，在 `sys.usb.config`
   被改成 mtp/none 时把 adb 加回去。
6. **USB 网络共享（Mac 只支持 NCM）**：`settings put global tether_force_usb_functions 1` 后报
   `could not enable IpServer for function NCM`——Tethering 的 `config_tether_ncm_regexs` 不匹配联想内核的 `usb0`
   → RRO 改为 `usb\d,ncm\d`。之后 IPv4 地址 250 ms 就被删掉——EthernetTracker 的默认正则 `(usb|eth)\d+`
   也抢了 usb0 → 第二个 RRO 把 `config_ethernet_iface_regex` 改为 `eth\d+`。
7. **激活锁 `cloudsp_fid 参数不能为空`**：小米"查找设备"用小米 TEE 里的 TA 签名，联想固件里没有，永远过不了。
   开机向导阶段用 `TB_NO_FINDDEVICE=1` 的 super（不含 MIUIFindDeviceCN），设置完成后再刷带查找设备的 super。
8. **"设置 → 小米账号"重新验证崩溃 / "查找 Pad 检查状态出错"**：账号 app 绑定查找设备服务失败会抛异常；
   而查找设备本身因为没有 TEE 永远报错。办法：`ro.build.version.incremental` 加 `.DEV` →
   `IS_STABLE_VERSION=false` → 账号 app 忽略查找设备的检查错误。**不要打开"查找设备"。**
9. **人脸解锁**：yupei 的 features 要求 TEE 人脸 HAL（本机没有 `face` 服务）。换用 HyperOS 3 的 PearlBiometric
   并设 `support_tee_face_unlock=false`，走非 TEE 路径，录入和解锁正常（重启后第一次需先输 PIN）。
10. **超级小爱专家模式**（`真机校验参数缺失` 62001）：需要小米 TEE 或安全芯片签名，无法解决。快速模式可用。
11. **无线副屏（Mac AirPlay → 小米"无线副屏"）颜色发灰发绿**：接收端用 TextureView 显示，HWUI 的 Skia/Vulkan
    按 BT.601 limited 做 YCbCr 转换。`debug.hwui.renderer=skiagl` 后误差从 5.8/9.4 降到 3.9/3.9。
    走 USB NCM 时 Mac 会发 HEVC，接收端只解 H.264 → 回退到 1080p；走 WiFi 则是 H.264 Retina。
    测量脚本见 `extras/mac_airplay_icc/`。
12. **手写笔（Lenovo Tab Pen Plus）**：BLE HID（17EF:617F）按键 + 触摸芯片的笔通道（`NVTCapacitivePen`，
    压感 0–4095、倾斜 ±60°）。硬件功能完整；小米"手写笔"设置页只认小米笔的 VID/PID，显示"未连接"，
    改它需要平台签名的 Settings，不做。笔的单键映射：单击返回、双击截屏、三击主页、长按多任务。

## 不要做的事

- **不要原始备份/恢复 userdata 来"回滚"**：QTEE 的安全存储在 `/data/vendor/tzstorage`，防回滚计数在 RPMB。
  中间只要开过一次机，旧快照就会被判回滚，Gatekeeper/KeyMint 报 `IKMHal_sendCmd status -30`，
  锁屏 PIN 永远解不开，CE 数据无法解密。迁移数据请用系统内的文件级备份，并先退出小米账号。
- 不要打开"查找设备"。
