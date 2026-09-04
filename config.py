import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

LLM_MODEL = os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")

LLM_PROVIDERS = {
    "deepseek": {
        "label": "DeepSeek", "model": "deepseek-v4-flash",
        "key_env": "DEEPSEEK_API_KEY", "base_url": "https://api.deepseek.com/v1",
        "adapter": "openai",
    },
    "openai": {
        "label": "OpenAI", "model": "gpt-5-nano",
        "key_env": "OPENAI_API_KEY", "base_url": "https://api.openai.com/v1",
        "adapter": "openai",
    },
    "qwen": {
        "label": "通义千问", "model": "qwen-flash",
        "key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "adapter": "openai",
    },
    "gemini": {
        "label": "Gemini", "model": "gemini-2.5-flash",
        "key_env": "GEMINI_API_KEY", "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "adapter": "gemini",
    },
    "anthropic": {
        "label": "Anthropic", "model": LLM_MODEL,
        "key_env": "ANTHROPIC_API_KEY", "base_url": None, "adapter": "anthropic",
    },
    "ollama": {
        "label": "Ollama（本地）", "model": "qwen2.5:3b",
        "key_env": None, "base_url": "http://127.0.0.1:11434", "adapter": "ollama",
    },
}


def get_llm_provider(name: str) -> dict:
    try:
        return LLM_PROVIDERS[name]
    except KeyError as exc:
        raise ValueError(f"不支持的模型供应商: {name}") from exc

# ACE-Step 1.5 集成配置。
# 官方: https://github.com/ace-step/ACE-Step-1.5
# ⚠ project_root / checkpoint_dir 为机器相关路径，权重首次运行自动下载；
#   在 Colab 冒烟测试时以实际 clone/下载位置为准，可用环境变量覆盖。
ACESTEP_PROJECT_ROOT = os.environ.get(
    "ACESTEP_PROJECT_ROOT", os.path.join(os.path.dirname(BASE_DIR), "ACE-Step-1.5")
)
ACESTEP_CHECKPOINT_DIR = os.environ.get(
    "ACESTEP_CHECKPOINT_DIR", os.path.join(ACESTEP_PROJECT_ROOT, "checkpoints")
)
ACESTEP_CONFIG = os.environ.get("ACESTEP_CONFIG", "acestep-v15-turbo")
ACESTEP_LM_MODEL = os.environ.get("ACESTEP_LM_MODEL", "acestep-5Hz-lm-0.6B")


def acestep_backend(device: str) -> str:
    """按设备选择 5Hz 语言模型后端。

    本项目默认面向 8GB 显存设备；ACE-Step 官方建议这一档在 Windows
    使用 PyTorch 后端，避免 vLLM 与 DiT 同时常驻导致显存不足。
    """
    return "mlx" if device == "mps" else "pt"


def get_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def ensure_dirs() -> None:
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)


# Web 后端配置
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "ze_music.db"))
APP_PASSCODE = os.environ.get("APP_PASSCODE", "")
CORS_ORIGINS = [
    o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()
]

# Cloudflare R2（S3 兼容）
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY", "")
R2_SECRET_KEY = os.environ.get("R2_SECRET_KEY", "")
R2_BUCKET = os.environ.get("R2_BUCKET", "")
R2_PUBLIC_BASE = os.environ.get("R2_PUBLIC_BASE", "")  # 如 https://xxx.r2.dev
