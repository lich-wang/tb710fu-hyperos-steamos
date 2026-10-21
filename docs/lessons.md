# 踩过的坑

按"代价"排序，越靠前越疼。

1. **userdata 原始镜像不能用来"回滚"**。QTEE 的安全存储在 `/data/vendor/tzstorage`，防回滚计数在 RPMB。
   备份之后只要开过一次 HyperOS，再写回旧镜像，Gatekeeper/KeyMint 就会报 `IKMHal_sendCmd status -30`：
   PIN 永远解不开，CE 数据永久无法解密。只能重新开机向导。迁移数据要用系统内的文件级备份。
2. **小米查找设备 / 激活锁**：依赖小米 TEE 里的 TA，联想固件没有。开机向导阶段先刷不带 FindDevice 的 super，
   之后再加回去，并在 incremental 末尾加 `.DEV` 让账号 app 忽略检查错误。永远不要打开"查找设备"。
3. **运行中 unbind 或 rmmod 已绑定的 nvt 触摸驱动**：输入子系统卡死，logind 跟着卡住，ssh 能认证但建不了会话，
   只能长按电源强制重启。重新加载只能在探测失败（设备未绑定）时做。
4. **强制重启会丢掉刚写的文件**：装完配置紧接着系统卡死，文件变成 0 字节（编译过的 hwdb 还在，一时看不出来）。
   写完关键文件要 `sync`，发布前检查有没有 0 字节文件。
5. **UFS 上 `dd oflag=direct bs=4M` 会挂死**：某个写请求永不返回，dd 进入 D 状态。用普通缓冲写 + `conv=fsync`。
6. **SteamOS 的 `/etc` 是 overlay，systemd 读单元时它还没挂载**：mask 和 wants 链接写进上层 `/etc` 不生效，
   要写底层 `/etc`。曾因 `home.mount` 等不到设备而黑屏、ssh 卡死。
7. **往合并 /usr 的根目录 `tar xf … -C /` 一个带 `lib/` 的包**：`/lib -> usr/lib` 符号链接被替换成目录，
   动态链接器失效，整个系统起不来。要么 `--keep-directory-symlink`，要么直接 `-C /usr/lib/...`。
   （修复时，Android 的 loop 设备在 4K 扇区的 UFS 上读出 EIO，只能用 `dmctl create … linear` 映射。）
8. **WirePlumber 规则的文件名顺序**：后加载的规则覆盖前面的。别的机型的规则匹配了同一个声卡名，
   把我们的 pro-audio 盖成了 UCM，Steam 因为没有音频输出而段错误，表现为黑屏。
9. **在内核树里 `git commit`**：`LOCALVERSION_AUTO` 让版本号带上新哈希，所有模块都找不到。关掉它，版本号固定。
10. **macOS 上 `mkfs.erofs` 默认 16K 块**：设备内核不支持，刷入即崩。显式 `-b4096`。
11. **busybox `nbd-client` 默认 4K 块**：MBR 分区算错。`-b 512`。`nbd-server -d` 只服务一个连接就退出，要用常驻模式。
12. **macOS 默认路由走有线网卡时**，同网段的 WiFi 设备不通（包括小米投屏的视频流）。调整网络服务顺序，或 `ssh -b`。
13. **x86 Linux 原生游戏在 FEX 下用的是转译的 x86 显卡驱动**，可能出现 GPU 命令流错误。优先用 Proton ARM64 跑 Windows 版。
