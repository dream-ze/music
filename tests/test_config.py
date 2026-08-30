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
