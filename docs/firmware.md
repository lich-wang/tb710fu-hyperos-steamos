# 固件清单

本仓库**不包含任何固件**（联想、高通、Awinic、Novatek 的二进制都不能再分发）。下面是 SteamOS 下需要的文件，
按 `/usr/lib/firmware/` 的目录结构放好，交给 `steamos/install_payload.sh`。
"本机"指从你自己设备的 HyperOS 里取（需要 root），例如 `adb shell su -c 'tar c /vendor/firmware_mnt/image' > image.tar`。

| 路径（相对 /usr/lib/firmware） | 来源 | 用途 |
|---|---|---|
| `qcom/sm8650/xiaoxin/gt/adsp.mdt`、`adsp.b*`、`adsp_dtb.*` | 本机 `/vendor/firmware_mnt/image/` | ADSP（音频、电池、USB-C） |
| `qcom/sm8650/xiaoxin/gt/cdsp.mdt`、`cdsp.b*`、`cdsp_dtb.*` | 同上 | CDSP |
| `qcom/sm8650/xiaoxin/gt/adspr.jsn`、`adsps.jsn`、`adspua.jsn`、`cdspr.jsn`、`battmgr.jsn` | 同上 | 保护域描述（pd-mapper） |
| `qcom/sm8650/xiaoxin/gt/gen70900_zap.mbn` | 本机 vendor 固件 | GPU zap shader（必须用本机签名的版本） |
| `qcom/gen70900_sqe.fw`、`qcom/gen70900_aqe.fw`、`qcom/gmu_gen70900.bin` | [linux-firmware](https://gitlab.com/kernel-firmware/linux-firmware) | Adreno 750 |
| `ath12k/WCN7850/hw2.0/amss.bin`、`m3.bin`、`board-2.bin` | linux-firmware / tb710fu-linux | WiFi（板级条目由 `board_name` 参数强制） |
| `qca/hmtbtfw20.tlv`、`qca/hmtnv20.*` | linux-firmware | 蓝牙 |
| `novatek/novatek_nt36532_fw.bin` | 本机 vendor 固件（`novatek_ts_fw.bin` 改名） | 触摸芯片（驱动探测时刷写） |
| `qcom/sm8650/Lenovo-TB710FU-tplg.bin` | 由 tb710fu-linux 的拓扑修改：唯一的 I2S_SINK 模块 ID `0x0700100A` 原位改为 TDM_SINK `0x0700100E` | 音频拓扑 |
| `aw882xx_acf.bin`、`awinic/aw88461_tb710fu.bin` | tb710fu-linux 的 board-root | AW882xx 功放参数 |

HyperOS 侧（`build_os4.py`）需要的输入也都来自你自己下载/提取的文件：
HyperOS 4 OTA 全量包（小米平板 8，`OS4.0.5.0.XPZCNXM`）、HyperOS 3 移植包、HyperOS 3 移植包里的
PearlBiometric、MIUIFindDeviceCN 等 APK。
