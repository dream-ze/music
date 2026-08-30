import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

LLM_MODEL = os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")

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
    """按设备选 5Hz 语言模型后端: CUDA->vllm, Apple->mlx, 其余->pt。"""
    return {"cuda": "vllm", "mps": "mlx"}.get(device, "pt")


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
