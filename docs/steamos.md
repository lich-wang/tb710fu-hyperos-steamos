# SteamOS

## 组成

- **用户空间**：[SteamOS-ARM-Port](https://github.com/hashtagbasit/SteamOS-ARM-Port) v1.4 的 sm8650 镜像
  （Valve Steam Frame 的 SteamOS 0.5.3；MBR：p1 FAT 512M、p2 ext4 根 11.3G、p3 ext4 home）。
  不刷它自带的 ROCKNIX ABL（锁 BL 的机器刷不了），而是用本项目的 kShimC 菜单 + 内核启动。
- **内核**：本项目的 7.2.6-tb710fu（[linux-kernel.md](linux-kernel.md)），镜像里自带的 7.2.8 内核不用。
- **本仓库的 `steamos/`**：
  - `rootfs/`：要叠加到系统里的服务、脚本和配置（目录结构与系统一致）；
  - `install_payload.sh`：安装模块、固件和 rootfs；
  - `steamos_install_ufs.sh`：把正在运行的 SteamOS 搬到 UFS 分区；
  - `patches/`：gamescope-session 补丁；
  - `tools/`：Steam 配置和游戏库的辅助脚本。

## 第一步：用电脑上的网络根盘（NBD）试跑

不动平板存储，先确认能跑：

1. 解压镜像，扩大 home 分区（建议 64 GB 稀疏文件），挂载分区（`docker/nbd-server/mnt.sh`，`RO=0`），
   在 arm64 环境里 `ROOT=<挂载的根> steamos/install_payload.sh modules.tar firmware/`。
2. 在电脑上跑 NBD 服务（`docker/nbd-server`，export 名 `steamos`）：
   必须用常驻模式 `sh -c 'nbd-server -C /etc/nbd-server/config; exec sleep infinity'`——`-d` 模式只服务一个连接就退出。
3. 打包一个 bootargs 带 `tb710fu.nbd nbd.max_part=8` 的 boot（`kernel/initramfs/init` 会走 NBD）。
   USB NCM 实测 271 MB/s。试跑期间不能拔线，电脑不能休眠（macOS：`caffeinate -dims`）。

## 第二步：装到 UFS

256 GB 机型的切分（`steamos/steamos_install_ufs.sh`，在 NBD 启动的 SteamOS 里以 root 运行）：

| 分区 | 范围（4 KiB 扇区） | 大小 | 用途 |
|---|---|---|---|
| sda14 `userdata` | 5105064–27836415 | 86.7 GiB | HyperOS（名称、类型、唯一 GUID 不变） |
| sda15 `steamos` | 27836416–61390842 | 128 GiB | SteamOS（ext4 `steamos-root`，根和 home 合一） |

脚本会清零 userdata 和 metadata 的头部，HyperOS 下次开机会重新格式化，**相当于恢复出厂**，务必先备份。
装好后 initramfs 会优先找分区名 `steamos`。

## 坑（都已在脚本里处理）

- **`/etc` 是 overlay**（upper = `/var/lib/overlays/etc/upper`），而且 systemd 读单元文件时它还没挂载：
  屏蔽（mask）和启用链接都要写在**底层** `/etc`（`mount --bind / /mnt` 后写 `/mnt/etc`）。
  upper 里还有一份自己的 `fstab`，会覆盖底层的。`rsync -x` 复制根目录时会漏掉底层 `/etc`。
- **`home.mount`** 等 `/dev/disk/by-partsets/shared/home`，UFS 安装后没有这个设备 → 所有登录会话
  （sddm 自动登录、ssh）都卡到超时，表现为黑屏 → 屏蔽；`steamos-sm8550-expand-home` 也屏蔽。
- **firewalld 拦截 usb0 上的 DHCP** → usb0 加入 trusted zone。
- **steamos-manager 缺 `/dev/uinput` 就退出**，gamescope 会一直等它（黑屏）→ 内核开 `INPUT_UINPUT`。
- NetworkManager 连接里绑定了旧网卡名（如 `wlp1s0`，SteamOS 下是 `wlan0`）→ 去掉 `interface-name`。
- 扫码登录一直转圈：二维码是断网时生成的，重启 `steam.service` 重新生成。
- **改 Steam 的 `localconfig.vdf` / `config.vdf` 之前先 `systemctl --user stop steam.service`**，否则会被覆盖。

## 音频

见 [linux-kernel.md](linux-kernel.md#音频4-aw882xxtdm)。用户空间部分：
- WirePlumber 规则 `56-tb710fu-audio.conf`：声卡用 pro-audio（关 UCM/ACP 自动切换），`pro-output-0` =「TB710FU 扬声器」，
  S16LE、不挂起。**文件名必须排在移植版自带的 `53-konkr-audio.conf` 之后**——那条规则匹配同一个声卡名，
  会把声卡切到 UCM "HiFi"，这台机器上没有扬声器 sink，只剩 `auto_null`，Steam 的音频模块随即段错误、每 4 秒重启一次（黑屏）。
- `57-tb710fu-noinput.conf`：禁用 pro-audio 的输入节点。麦克风通路没接，那个节点会让 WirePlumber 启动时卡在加载模块上
  （卡住时 `systemctl restart` 也会挂，只能 `kill -9`）。

## 触摸与手写笔

gamescope 自带的触摸模式只有"触摸 = 某一个鼠标键"（1 左、2 右、3 中）、悬停（0）和原生直通（4）：
没有右键、没有缩放，转视角的游戏（Unity 等读原始鼠标位移）也没法拖。

**`tb-touch-gestures`**（用户服务，`steamos/rootfs/usr/local/bin/`）：游戏获得焦点且保存的模式不是 4 时，独占触摸屏和笔，
把手势变成鼠标输入：

| 手势 | 鼠标 |
|---|---|
| 单指轻点 | 左键单击 |
| 单指按住移动 | 左键拖拽 |
| 单指长按 0.45 秒 | 右键（松开 = 右键单击；继续移动 = 右键拖拽） |
| 双指轻点 | 右键单击 |
| 双指一起移动 | 右键拖拽（旋转视角；`TB_TWO_FINGER_BUTTON=2` 改为中键） |
| 双指捏合 / 张开 | 滚轮（缩小 / 放大） |
| 笔悬停 / 笔尖 / 按住侧键点 / 第二侧键 | 移动 / 左键 / 右键 / 中键 |

实现要点（都是实测出来的）：
- 光标定位用 **XTEST**，发到焦点游戏所在的 Xwayland（通常 `:1`）。gamescope 经 libei 把 XTEST 的坐标映射到**焦点窗口**的坐标系；
  窗口在屏幕上按 `min(铺满所需倍数, --max-scale)` 放大并居中（SteamOS 会话里 `--max-scale 2`），触摸坐标按此反算。
- 按键、滚轮，以及右/中键按住期间的移动，来自一个**虚拟相对鼠标**（uinput）。只有真正的相对位移才能让游戏转视角；
  uinput 的"绝对坐标鼠标"gamescope 不接受；滚轮必须同时发 `REL_WHEEL_HI_RES`。
- 只在屏幕上没有手指时切换独占状态：手指按着时开始独占，gamescope 就收不到这根手指的抬起，它的左键会一直卡在按下状态。
- 进程异常退出时，uinput 设备随之销毁，按下的键会自动释放（XTEST 按下的键不会，所以不用 XTEST 发按键）。
- 回到 Steam 界面（appid 769）时放开触摸屏，恢复原生触摸滑动；笔在 Steam 界面里转成单指触摸。
- 笔扫描开关：udev 规则 `61-tb710fu-pen.rules` 在笔设备出现时写 `/proc/support_pen`。

`tb-touch-auto` 仍负责 gamescope 自己的模式（Steam 界面 4、游戏里用保存的模式），作为手势服务停止时的后备。
`tb-touch-mode 1|4` 和库里的两个快捷方式决定游戏里用"手势"（1）还是"原生触摸"（4，给原生支持触摸的游戏）。

测试工具：`steamos/tools/mt.py`（脚本化多点触摸：tap、tap2、hold、drag、pan2、pinch）和 `btn.sh`（查看游戏 X 服务器上哪些键按着）可以配合 `TB_TOUCH_NAME="…"` 让服务接管一个虚拟触摸屏，
用于在不碰平板的情况下脚本化测试手势。

## 电池

`qcom_battmgr` 读数正常。到 80% 显示"未充电"，是 Steam 设置里的充电上限（SteamOS 写入 `charge_control_end_threshold`），可在设置里改。

## 睡眠

内核默认选 `deep`（固件声明了 PSCI SYSTEM_SUSPEND）。10/21 实测深度睡眠前两次能唤醒，第三次一直没醒，只能长按电源强制重启。
SM8650 掌机内核（ArmadaOS 的 s2idle 补丁系列、SteamOS-ARM-Port）都是围绕 s2idle 做的，所以用
`/etc/systemd/sleep.conf.d/tb710fu-s2idle.conf`（`MemorySleepMode=s2idle`，放在底层 /etc）固定为 s2idle：睡眠与电源键唤醒实测正常。
唤醒时触摸芯片的固件可能要重试两三次才能加载成功（日志里的 `nvt_check_fw_reset_state failed` 属于这种情况），最终能恢复。

## 游戏兼容（ARM64）

运行方式：
- **Windows 游戏**：Proton ARM64（ARM64EC）+ FEX。Wine、系统库、显卡驱动都是原生 arm64，只有游戏代码被转译。
- **Linux x86 原生游戏**：整个进程由 FEX 转译，**包括 x86 版 Mesa/zink/Turnip 显卡驱动**。
- 原生 ARM64 Linux 版：目前很少（如 Celeste、Factorio 的 beta 分支），Steam 通过 `SteamLinuxRuntime_steamrt4-arm64` 运行。
- Android 版：Valve 的 Lepton 兼容层（主要是 VR 游戏）。

实测案例：Kingdom Rush 的 Linux 版（LÖVE 引擎，OpenGL）在 FEX 下启动约 7 秒，GPU 就报 `CP opcode error`
（读到全 0 的命令），接着 `zink: DEVICE LOST`、崩溃。试过 TU_DEBUG（sysmem、nolrz、noubwc、flushall）、
zink 选项、OpenGL ES、关 GPU 抢占、FEX GL thunk，都无效。主机的 Mesa 也只有 zink，没有 freedreno 原生 GL。
**强制使用 Proton 11.0 (ARM64) 跑 Windows 版后正常**。推测是 x86 版 Turnip 在 FEX 下写命令缓冲时出问题（未证实）。

因此建议：**Linux x86 原生游戏出问题，就在属性 → 兼容性里强制 Proton 11.0 (ARM64)**。批量设置可以用
`steamos/tools/addcompat.py`（写 `config.vdf` 的 CompatToolMapping，工具名 `proton_11-arm64`）。
`steamos/tools/frame_rt.py` 会扫描本机的 `appinfo.vdf`，列出每个游戏 Valve 给 Steam Frame 推荐的运行方式
（`steam_frame_compatibility/recommended_runtime`）以及是否有 arm64 映射。

## 远程访问

- `tools/mac/tbsos 'cmd'`：ssh 到 steamos@172.16.42.1（USB）；`-s` 以 root 运行，sudo 密码从 `$TB_SUDO_PASS`
  或 `~/.config/tb710fu/steamos-password` 读，**不要提交到仓库**。DHCP 不通时用 `tbsos6`（IPv6 链路本地地址）。
- `tools/mac/tbboot android|linux`：切换系统。

## 待办

- 外接 U 盘 / 移动固态做游戏库：内核加 `USB_UAS`、`EXFAT_FS` 模块；实测 OTG 主机模式和速度；在 SteamOS 设置 → 存储里格式化（ext4，会清空）。
- 麦克风、耳机、摄像头。
