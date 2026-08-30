import requests

import config
from src import credentials


class LLMError(RuntimeError):
    """可安全展示给用户的文本模型调用错误。"""


def _required_key(provider: str, temporary_key: str | None) -> str | None:
    provider_config = config.get_llm_provider(provider)
    key = credentials.resolve_key(provider, temporary_key)
    if provider_config["key_env"] and not key:
        raise LLMError(f"未配置 {provider_config['key_env']}")
    return key


def _post(url: str, *, timeout: int, **kwargs):
    try:
        response = requests.post(url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response.json()
    except Exception:
        raise LLMError("模型服务请求失败，请检查 Key、网络和模型名称") from None


def _openai_compatible(prompt, system, provider_config, model, api_key, timeout):
    data = _post(
        f"{provider_config['base_url'].rstrip('/')}/chat/completions",
        timeout=timeout,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2048,
        },
    )
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        return ""


def _gemini(prompt, system, provider_config, model, api_key, timeout):
    data = _post(
        f"{provider_config['base_url'].rstrip('/')}/models/{model}:generateContent",
        timeout=timeout,
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": system or "You are a helpful assistant."}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 2048},
        },
    )
    try:
        return "".join(
            part.get("text", "") for part in data["candidates"][0]["content"]["parts"]
        ).strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        return ""


def _ollama(prompt, system, provider_config, model, timeout):
    data = _post(
        f"{provider_config['base_url'].rstrip('/')}/api/chat",
        timeout=timeout,
        json={
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        },
    )
    try:
        return data["message"]["content"].strip()
    except (KeyError, TypeError, AttributeError):
        return ""


def _anthropic(prompt, system, model, api_key, timeout):
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key, timeout=timeout)
        msg = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system or "You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in msg.content if getattr(block, "type", None) == "text"
        ).strip()
    except Exception:
        raise LLMError("Anthropic 请求失败，请检查 Key、网络和模型名称") from None


def complete(
    prompt: str,
    system: str = "",
    *,
    provider: str = "anthropic",
    model: str | None = None,
    api_key: str | None = None,
    timeout: int = 60,
) -> str:
    """经统一入口调用所选文本模型，返回纯文本。"""
    provider_config = config.get_llm_provider(provider)
    selected_model = (model or "").strip() or provider_config["model"]
    resolved_key = _required_key(provider, api_key)
    adapter = provider_config["adapter"]

    if adapter == "openai":
        text = _openai_compatible(
            prompt, system, provider_config, selected_model, resolved_key, timeout
        )
    elif adapter == "gemini":
        text = _gemini(prompt, system, provider_config, selected_model, resolved_key, timeout)
    elif adapter == "ollama":
        text = _ollama(prompt, system, provider_config, selected_model, timeout)
    elif adapter == "anthropic":
        text = _anthropic(prompt, system, selected_model, resolved_key, timeout)
    else:
        raise LLMError(f"供应商 {provider} 的适配器配置无效")

    if not text:
        raise LLMError("模型返回了空响应")
    return text
