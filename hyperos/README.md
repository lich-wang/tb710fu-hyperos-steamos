# HyperOS 侧文件

| 路径 | 说明 |
|---|---|
| `keylayout/Vendor_17ef_Product_617f.kl` | Lenovo Tab Pen Plus（BLE HID 17EF:617F）按键映射：单击 0x0C0600 → BACK、双击 0x0C0601 → SYSRQ（截屏）、三击 0x0C0602 → HOME、长按 0x0C0603 → APP_SWITCH。放到 `system/usr/keylayout/` |
| `sepolicy_compat.cil` | 补回 Android 17 平台策略删掉、但 HyperOS 3 vendor 策略仍引用的类型；由 `tools/sepolicy_fix.py` 生成，构建时追加到 `product_sepolicy.cil` |
| `overlay/src_tether/` | RRO：`com.android.networkstack.tethering` 的 `config_tether_ncm_regexs = [usb\d, ncm\d]` |
| `overlay/src_eth/` | RRO：`com.android.connectivity.resources` 的 `config_ethernet_iface_regex = eth\d+`（否则 EthernetTracker 抢走 usb0） |
| `magisk/hwui_gl/` | Magisk 模块：`debug.hwui.renderer=skiagl`（修无线副屏偏色；新构建已直接写进 product） |
| `magisk/finddevice/` | 曾用的 Magisk 模块骨架：加回 `MIUIFindDeviceCN` + incremental `.DEV`。APK 需从移植包自行取出放到 `system/product/priv-app/MIUIFindDeviceCN/` |
| `magisk/faceunlock/` | 曾用的 Magisk 模块骨架：PearlBiometric + `support_tee_face_unlock=false` 的 device_features。APK 和 xml 需自行准备 |

overlay 用 apktool 构建，用你自己的密钥签名（v1 签名即可，`targetSdk 29`，priority 200），
输出到 `work/overlay/TB710FUTetheringOverlay.apk` 和 `work/overlay/TB710FUConnectivityOverlay.apk`，`tools/build_os4.py` 会放进 product。

刷入后开启 USB 网络共享（Mac 需要 NCM）：
```
adb shell settings put global tether_force_usb_functions 1
```
然后在设置里打开"USB 网络共享"。
