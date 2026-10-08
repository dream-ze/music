# AI 歌曲生成器

输入歌词和一句风格描述，应用使用文本模型规划歌曲与整理歌词，再由本机 ACE-Step 1.5 生成音频。

## 启动

- **Mac**：`./run_api.sh`（已配成 LaunchAgent 自启），前端改动后执行 `scripts/build_web.sh`。
- **Windows**：双击 `start_music.bat`（即 `run_api.ps1`），前端改动后执行 `scripts\build_web.ps1`。完整迁移步骤见 [docs/windows-setup.md](docs/windows-setup.md)。

后端在 8000 端口同时提供网页和 API：本机打开 <http://localhost:8000>，公网经 Tailscale Funnel 访问。

## 文本模型

在“高级设置”中选择供应商：

| 供应商 | 默认模型 | 环境变量 |
|---|---|---|
| DeepSeek | `deepseek-v4-flash` | `DEEPSEEK_API_KEY` |
| OpenAI | `gpt-5-nano` | `OPENAI_API_KEY` |
| 通义千问 | `qwen-flash` | `DASHSCOPE_API_KEY` |
| Gemini | `gemini-2.5-flash` | `GEMINI_API_KEY` |
| Anthropic | `claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` |
| Ollama | `qwen2.5:3b` | 无 |

模型名可以在界面覆盖。API Key 可以临时输入，也可以点击“保存 Key”写入当前 Windows 用户的凭据管理器。保存后页面不会回显完整 Key；可用“删除 Key”清除。

Key 读取顺序为：当前界面输入、Windows 凭据管理器、环境变量。模型调用失败或没有配置 Key 时，应用会回退到默认歌曲规划和本地歌词分段，继续生成音频，并在页面显示回退状态。

Ollama 默认访问 `http://127.0.0.1:11434`，使用前需自行安装 Ollama 并执行：

```powershell
ollama pull qwen2.5:3b
```

## 测试

使用 ACE-Step 的 Python 环境运行：

```powershell
C:\Users\ASUS\Desktop\ACE-Step-1.5\.venv\Scripts\python.exe -m pytest -q
```
