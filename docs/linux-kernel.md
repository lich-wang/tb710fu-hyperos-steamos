# Linux 7.2.6 内核移植

总原则：**遇到问题先看 HyperOS/Android 是怎么做的**——读它的 dtbo/vendor DTB、vendor 配置、sysfs，
必要时在 HyperOS 上用 uprobe 抓参数，而不是盲改。

## 构建

```
docker build -t kernel-build docker/kernel-build
git clone https://github.com/mydanyi/armadaos-freedom freedom && git -C freedom checkout ba692d8
docker run --rm -v "$PWD":/repo:ro -v "$PWD/freedom":/freedom:ro -v "$PWD/out":/out \
           -v tb-kwork:/build kernel-build bash /repo/kernel/build.sh
```

- 内核树 = linux 7.2.6 + armadaos-freedom 的内核补丁和 DTS（"freedom-base"）+ `kernel/tb710fu-kernel-on-freedom.patch`。
  总补丁包含：tb710fu-linux 的面板/触摸/WiFi/音频补丁、从 7.3 回移植的 `sound/soc/qcom/`、本项目的所有修改、
  以及 kShimC 用的 DTS `sm8650-lenovo-tb710fu-kshim.dts`。
- 内核树必须放在 docker 卷里：macOS 的绑定目录大小写不敏感，解压内核会出错。
- 版本号固定为 `7.2.6-tb710fu`（关 `LOCALVERSION_AUTO`）。单独编模块时也要传 `LOCALVERSION=`，并且在整树里
  `make modules`——用 `M=` 外部编译出来的模块缺 `intree` 标记。
- `kernel/config-7.2.6-tb710fu` 是最终配置；`kernel/fragments/` 是在 arm64 defconfig 基础上加过的片段
  （SteamOS 需要的 overlayfs、binder、ntsync、uinput、nftables 等）。
- 必须内建（=y）的：`PHY_QCOM_QMP*`（initramfs 里要用 USB/UFS）、`BLK_DEV_NBD`、`gpucc_sm8650`、`llcc`（见 GPU）。
- **DTS 里的蓝牙地址**（`&uart14 … local-bd-address`）请改成你自己机器的（HyperOS：`getprop ro.odm.lenovo.btaddr`，小端字节序）。

## initramfs（`kernel/initramfs/`）

busybox-static + 三个脚本。`init` 依次尝试：
1. GPT 分区名 `steamos`（等 15 s）→ 挂载 → `switch_root`；
2. bootargs 有 `tb710fu.nbd` 时走 `nbdroot.sh`：建 USB NCM gadget + udhcpd，探测 172.16.42.2–.10 上的 10809 端口，
   `nbd-client -b 512 -N steamos`（busybox 默认 4K 块会算错 MBR 分区），挂载 `nbd0p2`；
3. 都失败则进 `diag.sh`：USB NCM + telnet 诊断 shell，10 分钟无人操作自动重启。

## 问题与处理

### 显示（NT36532 双 DSI + DSC，3200×2000@120）

| 现象 | 原因 | 处理 |
|---|---|---|
| 加载 dispcc 后黑屏（simpledrm 阶段） | dispcc 探测时重配显示 PLL，ABL 的扫描输出中断 | 原生显示前不加载 dispcc |
| 在 DTS 里禁用 dispcc 也黑屏 | rpmhpd sync_state 撤掉 MMCX 投票 | 节点保持启用，只是不加载驱动 |
| aw37503/背光驱动加载后黑屏 | 没有消费者的 aw37503 把 ENP/ENN 拉低 | 由面板驱动统一使能 |
| 原生面板首次使能后黑屏 | NT36532 冷启动"闩锁竞态" | 起桌面前做一次 DRM 关/开（`tb-panel-cycle-py`） |
| `rmmod msm` oops | msm_mdss_unregister 空指针 | 调试时只能重启 |

最终做法：`tb-native-display.service`（在显示管理器之前）按 aw37503 → sy7758 → dispcc → 面板 → msm
的顺序 `modprobe -i`，等带 DSI 连接器的 card 出现后做一次关/开。这些模块在 modprobe.d 里
`blacklist` + `install … /bin/false`，防止 udev 抢先加载。

HyperOS dtbo 的面板参数（参考）：每链路 1600×2000@120，h 138/8/16，v 26/2/232，1197960464 bps/lane，
DSC 1.2 bpc10 bpp8，slice 800×20，每包两片。tb710fu-linux 的驱动用 DSC 1.1/bpc8 也能出图。

### GPU（Adreno 750）

- 固件：`gen70900_sqe.fw`、`gen70900_aqe.fw`、`gmu_gen70900.bin`（linux-firmware）；zap 用**本机 vendor 的**
  `qcom/sm8650/xiaoxin/gt/gen70900_zap.mbn`。
- `gpucc_sm8650`、`llcc` 必须内建：做成模块、加载太晚时，GPU SMMU（3da0000）探测超时放弃，GPU 变成 `-ENODEV`，
  且 arm-smmu 不支持 sysfs 重新绑定，只能重启。
- **不要用 `msm separate_gpu_kms=1`**：gamescope 会打开只有 GPU 的那张卡，报 "not a KMS device"。
- 903 MHz：照 HyperOS vendor DTB 加 OPP（RPMh 384 = TURBO，ACD `0x882a5ffd`）。压测 3200×2000 约 300 分，GPU 51 °C，稳定。
- IFPC 不开（tb710fu-linux 的记录：开了会因 GMU 栅栏超时冻结）。

### WiFi（WCN7850 / ath12k）

| 现象 | 原因 | 处理 |
|---|---|---|
| 驱动不认板子 | 板级数据条目 | `board_name=…,qmi-board-id=255` |
| 下载时 oops（`dev_gro_receive`） | tb710fu-linux 的进程上下文轮询器与 NAPI 同时服务同一个 SRNG（MSI 其实能触发） | `ath12k tb_poll_off=1` |
| 只有 0.1–0.5 MB/s | `RX_FLAG_DUP_VALIDATED` 被去掉后，mac80211 把 AP 重传的 MPDU 当重复帧丢弃 → TCP 丢包、拥塞窗口塌缩 | `ath12k_wifi7 tb_hw_dedup=1` → 3+ MB/s，局域网 10–19 MB/s |
| 更差 | 试验性的 `tb_sw_reorder=1` | 不要用 |
| 运行时改 `tb_poll_ms` 死机 | — | 只在加载时设置 |
| MAC 不对 | ath12k 不读 DT 里的 MAC | NetworkManager `cloned-mac-address` |

HyperOS 参考：`/vendor/etc/wifi/kiwi_v2/WCNSS_qcom_cfg.ini`（NAPI、BA 窗口 1024、硬件 REO）。

### 音频（4× AW882xx，TDM）

| 现象 | 原因 | 处理 |
|---|---|---|
| DSP 拒绝启动音频图 | 拓扑在 SEC TDM 通路用的是 I2S_SINK，DSP 不接受 4ch/32bit | 照 HyperOS：uprobe `/vendor/lib64/libagm.so` 的 `configure_tdm_ep`，抓到 `PARAM_ID_TDM_INTF_CFG 0x0800101B`（lpaif 0、idx 1、sync_src 1、data_out 1、mask 0xF、**8 slot × 32 bit**）；拓扑模块改成 TDM_SINK `0x0700100E`，DTS 8 slot（BCLK 12.288 MHz） |
| 24 位输入让 ADSP 崩溃 | — | 前端只用 S16LE（WirePlumber 规则） |
| 只有一侧的两个喇叭响 | 前端是 2 声道，MFC 的 4 声道映射是 FL FR LS RS → 时隙 2/3 静音 | `audioreach_mfc_set_media_format` 在 `lenovo,tb710fu` 上映射为 FL FR FL FR（左 = 0x34+0x36，右 = 0x35+0x37） |
| 音量很小 | AW882xx（PID 2308）的音量在寄存器 0x05 的低 10 位 | 照 HyperOS：0x34/0x35 = 10，0x36/0x37 = 0；DSP 增益 0 dB（8192） |
| 声音时有时无 | 功放每次启动锁 TDM 时钟偶尔失败，PipeWire 空闲挂起会反复触发启动 | `session.suspend-timeout-seconds = 0` |
| 开机后没有声卡（约 3/4 的开机） | ADSP 先于 `qcom_pd_mapper` 就绪，audio PD 起不来（没有 GPR 设备） | `tb-adsp-audio-check`：25 s 内没有声卡就重启 ADSP，然后重跑 `tb-audio-init` |

### 触摸与手写笔（Novatek NT36532，SPI）

- 固件 `novatek/novatek_nt36532_fw.bin` 来自本机 vendor，驱动探测时会自动刷写。
- **探测竞态**：大约一半的开机里，驱动在约 7 s 时读芯片 trim 全为 0，报 "chip is not identified"，
  整个会话都没有触摸 → `tb-touch-check`：10 s 内没有 `NVTCapacitiveTouchScreen` 就重新加载模块（最多 3 次）。
  **不要对已经绑定的设备 unbind/rmmod**：会把输入子系统卡死，连 ssh 都登不进去。
- **手写笔**：HyperOS 的触摸节点有 `novatek,pen-support`，加上后驱动会注册 `NVTCapacitivePen`
  （X 0–32000、Y 0–20000、压感 0–4095、倾斜 ±60°），写 `/proc/support_pen` = 1 打开笔扫描（固件命令 0x7B 0x01）。
  驱动没有给坐标设物理分辨率，libinput 会忽略它（"missing tablet capabilities: resolution"）→ udev hwdb 设为
  117 单位/mm（12.7 寸 16:10 屏约 273.5×171 mm）。SteamOS 的处理见 [steamos.md](steamos.md)。

### 其他

- **蓝牙**：freedom 把 btqca 的 DT 地址检查注释掉了、改成按序列号生成；补丁让它优先使用 DT 的 `local-bd-address`。
- **USB**：双角色经 pmic-glink 的 UCSI（需要 ADSP）；对电脑是 device/sink。USB NCM 偶尔枚举后无载波 →
  `tb-usb-ncm-watch` 检测到就解绑再绑定 UDC。
- **电池**：`qcom_battmgr`（pmic-glink）。充电上限由 SteamOS 的 `charge_control_end_threshold` 控制。
- **CPU**：设备只有 6 个核，DT 里多出的 cpu1/cpu2 会报 `psci: failed to boot (-22)`，无害。
- **看门狗**：Gunyah 下没有可用的 watchdog。
- **电源键**：logind 短按忽略、长按关机（默认短按就关机）。

## 远程调试

- USB NCM：平板 172.16.42.1，电脑拿到 .2–.10。macOS 只支持 NCM，不支持 RNDIS。
- WiFi：按 MAC 在 ARP 表里找 IP（`tools/mac/tbssh`）。如果电脑默认路由走有线网卡，同网段的 WiFi 设备可能连不上，要 `ssh -b <WiFi 地址>`。
- HyperOS 上抓参数：内核 kprobe 只能读内核内存；用户态参数用 uprobe（`/sys/kernel/tracing/uprobe_events`）。
