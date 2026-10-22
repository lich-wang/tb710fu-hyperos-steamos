# TB710FU 免解锁双系统：小米澎湃 OS 4 + SteamOS

在 **不解锁 Bootloader** 的联想小新 Pad Pro GT（TB710FU，骁龙 8 Gen 3 / SM8650）上，
同时运行 **小米澎湃 OS 4（HyperOS 4，Android）** 和 **SteamOS（ARM64，Valve Steam Frame 同源）**，
开机时通过菜单选择系统，也可以在任一系统里一条命令切换到另一个。

> 本项目的逆向分析、代码、补丁和文档主要由 AI 编程助手在作者的指导下完成；
> 作者负责设备操作、方案决策和每一步的实机验证。

> ⚠️ **风险提示**：本项目涉及 9008（EDL）线刷、分区表修改和启动镜像替换，操作失误可能导致设备无法开机、
> 数据丢失或失去保修。设备唯一数据分区（`persist`、`modemst1/2`、`fsg`、`fsc`、`devinfo`、`frp`、
> `keystore`、`ssd`、`secdata`、`uefivarstore`、`cdt`、`ddr`）**任何时候都不要写**，动手前先完整备份。
> 一切后果自负。

## 效果

| 系统 | 状态 |
|---|---|
| **HyperOS 4**（小米平板 8 底包移植） | 日常可用：显示 3200×2000@120Hz、WiFi/蓝牙、相机、传感器、音频、小米账号、人脸解锁、Magisk root、USB 网络共享（NCM）、无线副屏 |
| **SteamOS**（SteamOS-ARM-Port 用户空间 + 本项目内核） | 日常可用：原生 DSI 屏幕、Adreno 750 GPU（Turnip/Vulkan，903 MHz）、WiFi 7、4 扬声器立体声、触摸、手写笔、电池、USB 双角色、Steam 登录与 Proton/FEX 游戏 |
| **开机菜单**（kShimC） | 音量键选择、超时默认项，`tbboot android\|linux` 一键切换 |

已知限制：
- 小米"查找设备"、超级小爱专家模式依赖小米专有 TEE/安全芯片，无法使用（不要打开查找设备）。
- SteamOS 下麦克风、耳机、摄像头未适配；手写笔按"手指"处理（无压感/悬停）。
- 只有一个 USB-C 口；外接 U 盘做游戏库尚未实测（见 [docs/steamos.md](docs/steamos.md)）。

## 原理一览

```
ABL（未解锁，信任 AOSP testkey）
 └─ boot_a = kShimC + 原 GKI 6.1 内核 + Linux 7.2.6 内核 + DTB   （testkey 重新签 AVB footer）
      ├─ 菜单 "HyperOS" → GKI 6.1 → vendor_boot(ext4+erofs fstab) → super(HyperOS 4 system/product + HyperOS 3 vendor)
      └─ 菜单 "SteamOS" → Linux 7.2.6-tb710fu → initramfs → UFS 分区 sda15 (ext4 "steamos")
```

- **为什么锁 BL 也能刷**：这台机器的 ABL 信任 AOSP 公开测试密钥（`testkey_rsa4096`），
  社区"免解锁补充包"正是利用这一点。我们只替换 A 槽的 boot/vendor_boot/vbmeta 并用同一测试密钥签名，
  同时保持防回滚索引不低于设备记录。详见 [docs/boot-chain.md](docs/boot-chain.md)。
- **双系统**：boot_a 里放 [kShimC](https://github.com/sunflower2333/kShimC) 开机菜单，
  它在 ABL 之后、内核之前运行，根据选择把控制权交给 Android 内核或 Linux 内核。
- **存储**：userdata 缩小到约 87 GiB 给 HyperOS，新建 128 GiB 分区给 SteamOS（256 GB 机型）。

## 文档

| 文档 | 内容 |
|---|---|
| [docs/flash-guide.md](docs/flash-guide.md) | **刷机指南**：从官方系统到双系统的完整步骤 |
| [docs/boot-chain.md](docs/boot-chain.md) | 锁 BL 启动原理、AVB/防回滚、EDL 备份与线刷、救砖（900E） |
| [docs/hyperos4.md](docs/hyperos4.md) | HyperOS 4 移植：底包选择、改动清单、构建与刷入、排错记录 |
| [docs/dualboot-kshim.md](docs/dualboot-kshim.md) | kShimC 开机菜单：打包签名、SM8650 屏幕读取、MMU 提速、系统切换 |
| [docs/linux-kernel.md](docs/linux-kernel.md) | Linux 7.2.6 内核移植：显示、GPU、WiFi、音频、触摸、蓝牙等的问题与处理 |
| [docs/steamos.md](docs/steamos.md) | SteamOS 安装（分区、payload）、触摸/手写笔/音频/游戏兼容、待办 |
| [docs/firmware.md](docs/firmware.md) | 需要从你自己设备上提取的固件清单（本仓库不含任何固件） |
| [docs/lessons.md](docs/lessons.md) | 踩过的坑：TEE 防回滚、overlay /etc、UFS 写挂死…… |

## 仓库结构

```
tools/          构建与刷机工具：make_v3_bootchain.py（v3 启动链）、build_os4.py（HyperOS 4 分区构建）、make_super.py、
                lp_unpack.py、erofs_meta.py、kshim_pack_boot.py / kshim_variants.sh（打包双系统 boot）、flash_super.sh、
                collect_firmware.sh、patch_tplg.py、mac/（切换与远程工具）
kshim/          kShimC 的 TB710FU 补丁、defconfig、构建脚本
kernel/         Linux 7.2.6 内核：总补丁（基于 armadaos-freedom）、.config、initramfs、可复现构建脚本 build.sh
steamos/        SteamOS 安装脚本、rootfs 叠加文件（服务/配置）、gamescope 补丁、Steam 辅助工具
hyperos/        HyperOS 侧：笔按键映射、SELinux 兼容策略、RRO overlay 源码、Magisk 模块
docker/         构建容器（内核、kShimC、NBD 服务器）
extras/         Mac 无线副屏色彩测量脚本
docs/           文档（刷机指南见 flash-guide.md）
AGENT.md        给 AI Agent 的刷机操作规程
work/           （不入库）你自己设备的备份、底包、构建产物
```

## 怎么刷

完整步骤：**[docs/flash-guide.md](docs/flash-guide.md)**——从联想官方 ZUI 1.5.04.495 开始，进 9008 备份，
线刷 HyperOS 3 移植包，换 v3 启动链，root，编译内核与开机菜单，SteamOS 先网络试跑再装进 UFS，最后刷入 HyperOS 4。

> **推荐用 AI Agent 来刷**：让一个能执行命令的 AI 编程 Agent 读取 [`AGENT.md`](AGENT.md)（操作规程：安全红线、
> 每次写入前的确认、各阶段检查点、已知故障）和刷机指南，由它执行命令、校验结果，需要你动手时它会停下来告诉你。

步骤概要：

1. 9008 备份 GPT 和所有分区（尤其唯一数据分区）。
2. `edl qfil` 线刷 HyperOS 3 移植包 → `tools/make_v3_bootchain.py` 生成 v3 启动链并写入 A 槽（输出与指南里的 sha256 逐字节一致）。
3. Magisk root → `tools/collect_firmware.sh` 收集本机固件。
4. `kernel/build.sh` 编译内核 → 编译 kShimC → `tools/kshim_variants.sh` 打包双系统 boot 写入 boot_a。
5. Mac 上 NBD 网络根盘试跑 SteamOS → `steamos/steamos_install_ufs.sh` 装进 UFS。
6. `tools/build_os4.py` + `tools/make_super.py` 构建 HyperOS 4 super → `tools/flash_super.sh` 刷入。

## 致谢与上游

| 项目 | 用途 |
|---|---|
| [kShimC](https://github.com/sunflower2333/kShimC) | 开机菜单 shim |
| [DualBootKernelPatcher](https://github.com/Project-Aloha/DualBootKernelPatcher) | 多内核打包器 |
| [armadaos-freedom](https://github.com/mydanyi/armadaos-freedom)、[ArmadaOS](https://github.com/armada-os/armada) | SM8650 内核补丁集与 kShimC 集成 |
| [tb710fu-linux](https://github.com/MeteoricmeteorLL/tb710fu-linux) | TB710FU 的 DTS、面板/触摸/音频/WiFi 补丁 |
| [SteamOS-ARM-Port](https://github.com/hashtagbasit/SteamOS-ARM-Port) | SM8650 版 SteamOS 用户空间镜像 |
| [audioreach-topology](https://git.codelinaro.org/linaro/qcomlt/audioreach-topology) | 音频拓扑 |
| [bkerler/edl](https://github.com/bkerler/edl) | 高通 9008 读写 |
| AOSP `avbtool` / `mkbootimg`、SELinux `secilc` | 签名、打包、策略编译 |
| 酷安 @兰微卡鱼 | HyperOS 3 移植包（vendor 与启动链的基础） |
| [FEX-Emu](https://github.com/FEX-Emu/FEX)、Valve 的 Proton ARM64 / Lepton | ARM 上运行 x86/Windows/Android 游戏 |

## 许可证

本仓库内容以 [GPL-2.0](LICENSE) 发布。第三方项目各自保留其许可证；本仓库不包含任何联想、小米、高通或 Valve 的二进制文件。
