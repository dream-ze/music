# 迁移到 Windows（免费方案）

目标机器：Windows 11 + RTX 4060 Laptop 8GB + 32GB 内存。迁移后所有环节都不额外花钱：出歌用本机显卡，公网访问用 Tailscale Funnel（免费），音频存储继续用 Cloudflare R2（免费额度内），文本 LLM 继续用 DeepSeek（按量计费，每首几分钱）。

> 2026-10-09 已在目标 Windows 电脑验证静态网页构建、后端测试与真实短曲生成。公网迁移和自启动步骤尚未验证。

## 先在当前电脑本地运行

本机已有 ACE-Step Python 环境、Node 和 FFmpeg，无需重新安装。运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_web.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File run_api.ps1
```

随后打开 http://localhost:8000 。启动与构建脚本会刷新系统/用户 PATH；前端默认使用当前网页所在地址的 API，不再绑定旧 Funnel 域名。分离部署可在构建前显式设置 `NEXT_PUBLIC_API_BASE`。若 8000 已被旧服务占用，先退出旧服务，或用 `run_api.ps1 -Port 8001` 启动并访问对应端口。

`AUDIO_STORAGE=auto` 是默认值：R2 完全未配置时保存到 `outputs/audio/`，完整配置时使用 R2。部分配置会明确报错，可通过 `AUDIO_STORAGE=local` 显式使用本地。每个任务的 WAV/工作文件放在 `outputs/jobs/<job_id>/`，旧的 R2 链接继续有效。本地音频使用随机文件名的公开媒体 URL（与原公开 R2 音频一致），支持拖动播放；下载和删除 API 仍校验口令。删除歌曲会清除发布的本地 MP3，任务原始文件保留。

Windows 启动默认选用 0.6B LM；`.env` 或进程环境中的显式设置优先。当前 PyTorch 2.7.1+cu128 / torchao 0.16.0 虽提示跳过不兼容 C++ 扩展，但 `int8_weight_only` 的 CUDA 运算和完整短曲生成均已通过，因此此次没有升级或降级依赖。其他量化路径未验证。

本机测试：固定中文歌词、caption、seed=42，0.6B/PT、Turbo 8 步、INT8、CPU/DiT offload，生成 45 秒音频并转换 MP3，首次加载在内用时约 51.2 秒。此测试直接调用音频生成器，不含外部文本 API、上传或听感评测。

## 0. 准备清单

| 软件 | 用途 | 安装 |
|---|---|---|
| NVIDIA 驱动（支持 CUDA 12.8） | 出歌 | GeForce Experience 或官网，装最新版 |
| Git | 拉代码 | `winget install Git.Git` |
| Node.js LTS | 构建网页 | `winget install OpenJS.NodeJS.LTS` |
| ffmpeg | WAV 转 MP3 | `winget install Gyan.FFmpeg`，装完**重开终端**，`ffmpeg -version` 能输出即可 |
| Tailscale | 公网访问 | `winget install Tailscale.Tailscale` |
| 7-Zip | 解压 ACE-Step 免安装包 | `winget install 7zip.7zip` |

## 1. 目录布局

两个目录放在同一个父目录下（示例用 `D:\music`，路径里避免中文和空格）：

```
D:\music\
  ACE-Step-1.5\     ← 出歌引擎
  zemusic\          ← 本项目
```

## 2. 安装 ACE-Step（推荐官方免安装包）

1. 下载 [ACE-Step-1.5.7z](https://files.acemusic.ai/acemusic/win/ACE-Step-1.5.7z)，解压到 `D:\music\ACE-Step-1.5`。包里自带 `python_embedded`，启动脚本会自动找到它。
2. **模型权重从 Mac 拷过去**（约 11GB，比在国内重新下载稳）：把 Mac 上 `~/ACE-Step-1.5/checkpoints/` 下的这些目录拷到 `D:\music\ACE-Step-1.5\checkpoints\`：
   - `acestep-v15-turbo`、`acestep-5Hz-lm-0.6B`、`Qwen3-Embedding-0.6B`、`vae`
   - 可选：`scragvae`（若要用 ScragVAE）、`acestep-5Hz-lm-1.7B`（8GB 显存不推荐）
3. 确认：`D:\music\ACE-Step-1.5\python_embedded\python.exe -c "import torch; print(torch.cuda.is_available())"` 输出 `True`。

## 3. 拉代码、装后端依赖

```powershell
cd D:\music
git clone https://github.com/dream-ze/music.git zemusic
cd zemusic
git checkout feat/song-generator-v0.1
D:\music\ACE-Step-1.5\python_embedded\python.exe -m pip install -r requirements-server.txt
```

## 4. 迁移配置和数据

从 Mac 拷两个文件到 `D:\music\zemusic\`（**含密钥，用 U 盘或局域网拷，不要发聊天工具**）：

- `.env`（密钥、口令、R2、DeepSeek）
- `ze_music.db`（作品库、分类、收藏；歌曲音频在 R2 上，链接继续有效）

然后打开 `.env`，**改 ACE-Step 相关的几行**：

```ini
ACESTEP_LM_MODEL=acestep-5Hz-lm-0.6B
ACESTEP_LM_BACKEND=pt
# 下面这行是 Mac 专用的，删掉或注释掉
# ACESTEP_MLX_VAE_FP16=1
```

不需要手动设置量化：代码检测到 8GB 显存会自动用 INT8 量化 + DiT offload（对齐 ACE-Step 官方 8GB 档位）。即使忘了改 `ACESTEP_LM_BACKEND=mlx`，非 Apple 设备上也会自动退回 `pt`。

## 5. 构建网页

```powershell
cd D:\music\zemusic
powershell -ExecutionPolicy Bypass -File scripts\build_web.ps1
```

确认：最后输出 `built web\out (API base: /)`，表示网页与 API 同源。

## 6. 先在本机跑通

双击 `start_music.bat`（或 `powershell -ExecutionPolicy Bypass -File run_api.ps1`）。确认：

1. 窗口里出现 `Uvicorn running on http://0.0.0.0:8000`；
2. 浏览器打开 <http://localhost:8000>，输入口令能进；
3. 提交一首短歌：第一首要加载模型（几分钟），之后看进度条走到「上传保存」并能播放。

## 7. 公网地址切换到 Windows

公网地址 `https://192.tail3eff52.ts.net` 由 Tailscale 节点名 `192` 决定，**同一时间只能有一台机器叫 `192`**。

1. **Mac 上先让出名字**（终端执行）：
   ```bash
   tailscale funnel --https=443 off
   tailscale set --hostname wisers-mac
   ```
   并停掉 Mac 后端：`launchctl bootout gui/$(id -u)/com.zemusic.backend`
2. **Windows 上**：打开 Tailscale 用同一账号登录，然后在管理员 PowerShell 里：
   ```powershell
   tailscale set --hostname 192
   tailscale funnel --bg 8000
   tailscale funnel status
   ```
3. 确认：`funnel status` 显示 `https://192.tail3eff52.ts.net (Funnel on)`，手机流量打开这个地址能进网站。

如果节点名变成了 `192-1`，说明旧设备还占着名字：到 Tailscale 管理后台（login.tailscale.com → Machines）把旧的 `192` 改名或删除，再执行一次 `tailscale set --hostname 192`。

## 8. 开机自启（免费）

**方式 A：任务计划程序（系统自带）**。管理员 PowerShell：

```powershell
schtasks /Create /TN "zemusic-backend" /SC ONLOGON /RL HIGHEST /TR "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File D:\music\zemusic\run_api.ps1 -Log"
```

日志写到 `D:\music\zemusic\backend.log`。缺点：进程崩溃后不会自动重启。

**方式 B：servy / NSSM（开源免费，能崩溃自动重启）**：把 `powershell.exe` 注册成服务，参数同上。需要“崩了自动拉起”时用这个。

Tailscale 安装后默认开机自启，Funnel 配置会保留。

## 9. 防休眠

设置 → 系统 → 电源：插电时“从不”睡眠；合盖操作设为“不采取任何操作”。出歌时插电，并在 NVIDIA 控制面板里给 Python 选“高性能 NVIDIA 处理器”。

## 回退到 Mac

Windows 上 `tailscale funnel --https=443 off` 并改名；Mac 上 `tailscale set --hostname 192`、`tailscale funnel --bg 8000`，再 `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.zemusic.backend.plist`。注意两边的 `ze_music.db` 会各自分叉，迁回时要把新的那份拷回去。

## 常见问题

| 现象 | 处理 |
|---|---|
| 启动时 `Python not found` | 检查目录布局；或在 `.env` 里加 `ZE_PYTHON=D:\...\python.exe` |
| `ffmpeg 转码失败` / 找不到 ffmpeg | 装 ffmpeg 后**重开终端**；计划任务要注销重新登录才拿到新 PATH |
| CUDA out of memory | `.env` 加 `ACESTEP_OFFLOAD_DIT=1`（默认已开）；确认没有别的程序占显存；歌太长时先试短歌 |
| 量化报错（torchao） | `.env` 加 `ACESTEP_QUANTIZATION=none` 关掉量化先跑通，再把报错贴给 Claude |
| 中文乱码 | 用 `start_music.bat` / `run_api.ps1` 启动（已设 `PYTHONUTF8=1`） |
