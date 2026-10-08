import os
import config


def test_get_device_returns_valid_value():
    assert config.get_device() in {"cuda", "mps", "cpu"}


def test_llm_model_has_default():
    assert isinstance(config.LLM_MODEL, str) and config.LLM_MODEL


def test_ensure_dirs_creates_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUTS_DIR", str(tmp_path / "out"))
    monkeypatch.setattr(config, "ASSETS_DIR", str(tmp_path / "assets"))
    config.ensure_dirs()
    assert os.path.isdir(config.OUTPUTS_DIR)
    assert os.path.isdir(config.ASSETS_DIR)


def test_llm_provider_registry_contains_supported_providers():
    assert set(config.LLM_PROVIDERS) == {
        "deepseek", "openai", "qwen", "gemini", "anthropic", "ollama"
    }
    assert config.get_llm_provider("deepseek")["model"] == "deepseek-v4-flash"
    assert config.get_llm_provider("ollama")["key_env"] is None


def test_acestep_lm_model_defaults_to_official_default():
    """5Hz LM 默认档必须跟官方 DEFAULT_LM_MODEL 一致。

    曾经写死 acestep-5Hz-lm-0.6B —— 一个没下载的目录。LLMHandler.initialize()
    找不到目录时只返回 (错误消息, False) 不抛异常,于是 LM 静默不启动,
    thinking/CoT 全程没跑,出歌却照常"成功"。
    """
    assert config.ACESTEP_LM_MODEL == "acestep-5Hz-lm-1.7B"


def test_configured_lm_model_exists_in_checkpoint_dir():
    """配置指向的 LM 目录必须真实存在(本机有 checkpoints 时才检查)。"""
    import pytest

    if not os.path.isdir(config.ACESTEP_CHECKPOINT_DIR):
        pytest.skip("本机没有 ACE-Step checkpoints")
    assert os.path.isdir(
        os.path.join(config.ACESTEP_CHECKPOINT_DIR, config.ACESTEP_LM_MODEL)
    )


def test_llm_provider_defaults_to_anthropic():
    """默认供应商不变;换供应商靠环境变量 LLM_PROVIDER,不改代码。"""
    assert config.LLM_PROVIDER == "anthropic"


def test_llm_provider_default_is_a_known_provider():
    assert config.LLM_PROVIDER in config.LLM_PROVIDERS


# ── 内存开关:16GB 统一内存装不下 DiT + 1.7B LM 同时常驻 ────────────────

def test_acestep_offload_enabled_on_shared_memory_devices():
    """cuda 和 mps 都要 offload。mps 是统一内存,得跟整个系统抢,实测
    turbo + 1.7B LM 同时常驻直接 MPS OOM。"""
    assert config.acestep_offload("cuda") is True
    assert config.acestep_offload("mps") is True
    assert config.acestep_offload("cpu") is False


def test_acestep_offload_can_be_overridden(monkeypatch):
    monkeypatch.setenv("ACESTEP_OFFLOAD", "0")
    assert config.acestep_offload("mps") is False
    monkeypatch.setenv("ACESTEP_OFFLOAD", "1")
    assert config.acestep_offload("cpu") is True


def test_acestep_backend_defaults_unchanged():
    assert config.acestep_backend("mps") == "mlx"
    assert config.acestep_backend("cuda") == "pt"


def test_acestep_backend_can_be_overridden(monkeypatch):
    """MLX 会跳过 CPU offload;内存不够时要能换成 pt 拿回 offload 能力。"""
    monkeypatch.setenv("ACESTEP_LM_BACKEND", "pt")
    assert config.acestep_backend("mps") == "pt"


def test_acestep_vae_defaults_to_none(monkeypatch):
    """未设置时交给上游决定(official),不在这里写死。"""
    monkeypatch.delenv("ACESTEP_VAE_CHECKPOINT", raising=False)
    assert config.acestep_vae() is None


def test_acestep_vae_can_be_overridden(monkeypatch):
    monkeypatch.setenv("ACESTEP_VAE_CHECKPOINT", " scragvae ")
    assert config.acestep_vae() == "scragvae"


def test_mlx_backend_override_ignored_off_apple(monkeypatch):
    """从 Mac 拷过来的 .env 带着 ACESTEP_LM_BACKEND=mlx,到 Windows/CUDA 上必须退回 pt。"""
    monkeypatch.setenv("ACESTEP_LM_BACKEND", "mlx")
    assert config.acestep_backend("mps") == "mlx"
    assert config.acestep_backend("cuda") == "pt"
    monkeypatch.setenv("ACESTEP_LM_BACKEND", "vllm")
    assert config.acestep_backend("cuda") == "vllm"


def test_dit_options_follow_vram_tiers(monkeypatch):
    for k in ("ACESTEP_QUANTIZATION", "ACESTEP_OFFLOAD_DIT"):
        monkeypatch.delenv(k, raising=False)
    # 8GB(如 RTX 4060 Laptop):INT8 + DiT 也 offload,对齐上游 tier3/4
    assert config.acestep_dit_options("cuda", vram_gb=8) == {
        "quantization": "int8_weight_only", "offload_dit_to_cpu": True}
    # 12–16GB:仍量化,DiT 可常驻
    assert config.acestep_dit_options("cuda", vram_gb=12) == {
        "quantization": "int8_weight_only", "offload_dit_to_cpu": False}
    assert config.acestep_dit_options("cuda", vram_gb=24) == {
        "quantization": None, "offload_dit_to_cpu": False}
    # Apple / CPU 不量化(上游对 MPS 也是 no quantization)
    assert config.acestep_dit_options("mps") == {"quantization": None, "offload_dit_to_cpu": False}


def test_dit_options_env_overrides(monkeypatch):
    monkeypatch.setenv("ACESTEP_QUANTIZATION", "none")
    monkeypatch.setenv("ACESTEP_OFFLOAD_DIT", "0")
    assert config.acestep_dit_options("cuda", vram_gb=8) == {
        "quantization": None, "offload_dit_to_cpu": False}
    monkeypatch.setenv("ACESTEP_QUANTIZATION", "fp8_weight_only")
    assert config.acestep_dit_options("mps")["quantization"] == "fp8_weight_only"
