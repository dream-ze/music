import os

import config

SERVICE_NAME = "ai-song-generator"

try:
    import keyring as _keyring
except ImportError:  # pragma: no cover - installation error has a readable path
    _keyring = None


def _require_keyring():
    if _keyring is None:
        raise RuntimeError("凭据组件未安装，请安装 keyring")
    return _keyring


def get_saved_key(provider: str) -> str | None:
    value = _require_keyring().get_password(SERVICE_NAME, provider)
    return value.strip() if value and value.strip() else None


def has_saved_key(provider: str) -> bool:
    return get_saved_key(provider) is not None


def save_key(provider: str, api_key: str) -> None:
    config.get_llm_provider(provider)
    value = (api_key or "").strip()
    if not value:
        raise ValueError("API Key 不能为空")
    _require_keyring().set_password(SERVICE_NAME, provider, value)


def delete_key(provider: str) -> None:
    config.get_llm_provider(provider)
    _require_keyring().delete_password(SERVICE_NAME, provider)


def resolve_key(provider: str, temporary_key: str | None = None) -> str | None:
    provider_config = config.get_llm_provider(provider)
    temporary = (temporary_key or "").strip()
    if temporary:
        return temporary
    saved = get_saved_key(provider)
    if saved:
        return saved
    env_name = provider_config["key_env"]
    return os.environ.get(env_name) if env_name else None
