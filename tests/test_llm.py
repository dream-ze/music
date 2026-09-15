import os
import pytest
from src import llm


def test_complete_is_callable():
    assert callable(llm.complete)


def test_complete_raises_readable_error_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(llm.credentials, "get_saved_key", lambda provider: None)
    with pytest.raises(llm.LLMError, match="ANTHROPIC_API_KEY"):
        llm.complete("hi")


class FakeResponse:
    def __init__(self, data, status_code=200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP failed with secret-in-body")

    def json(self):
        return self._data


def test_openai_compatible_provider_uses_registry(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(llm.requests, "post", fake_post)
    out = llm.complete("hello", system="sys", provider="deepseek", api_key="sekret")
    assert out == "ok"
    assert captured["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sekret"
    assert captured["json"]["model"] == "deepseek-v4-flash"


def test_gemini_provider_request(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse({"candidates": [{"content": {"parts": [{"text": "好"}]}}]})

    monkeypatch.setattr(llm.requests, "post", fake_post)
    assert llm.complete("你好", provider="gemini", api_key="g-key") == "好"
    assert "gemini-2.5-flash:generateContent" in captured["url"]
    assert captured["params"] == {"key": "g-key"}


def test_ollama_does_not_require_key(monkeypatch):
    monkeypatch.setattr(
        llm.requests, "post",
        lambda *a, **k: FakeResponse({"message": {"content": "local"}}),
    )
    assert llm.complete("hi", provider="ollama") == "local"


def test_provider_error_does_not_leak_key(monkeypatch):
    monkeypatch.setattr(
        llm.requests, "post", lambda *a, **k: FakeResponse({}, status_code=401)
    )
    with pytest.raises(llm.LLMError) as exc:
        llm.complete("hi", provider="openai", api_key="top-secret")
    assert "top-secret" not in str(exc.value)
    assert "secret-in-body" not in str(exc.value)


def test_empty_provider_response_is_error(monkeypatch):
    monkeypatch.setattr(
        llm.requests, "post",
        lambda *a, **k: FakeResponse({"choices": [{"message": {"content": ""}}]}),
    )
    with pytest.raises(llm.LLMError, match="空响应"):
        llm.complete("hi", provider="qwen", api_key="key")


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"), reason="需要真实 API key"
)
def test_complete_smoke():
    out = llm.complete("只回复一个字：好", system="你是测试助手")
    assert isinstance(out, str) and out.strip()


# ── DeepSeek 思考模式 / 空正文类型化 ─────────────────────────────────
#
# deepseek-v4-flash 默认开思考:断行这类任务会把 max_tokens 全花在
# reasoning_content 上,正文为空(finish_reason=length)。planner 的 JSON 任务
# 思考量小才一直"正常"。实测关掉思考后 1.5s 出正文且质量更好。

def test_deepseek_request_disables_thinking(monkeypatch):
    captured = {}
    monkeypatch.setattr(llm.requests, "post",
                        lambda url, **kw: captured.update(kw) or FakeResponse({"choices": [{"message": {"content": "ok"}}]}))
    llm.complete("hi", provider="deepseek", api_key="k")
    assert captured["json"]["thinking"] == {"type": "disabled"}


def test_other_openai_compatible_providers_do_not_send_thinking(monkeypatch):
    captured = {}
    monkeypatch.setattr(llm.requests, "post",
                        lambda url, **kw: captured.update(kw) or FakeResponse({"choices": [{"message": {"content": "ok"}}]}))
    llm.complete("hi", provider="openai", api_key="k")
    assert "thinking" not in captured["json"]


def test_empty_content_raises_typed_empty_response(monkeypatch):
    monkeypatch.setattr(llm.requests, "post",
                        lambda *a, **k: FakeResponse({"choices": [{"message": {"content": ""}}]}))
    with pytest.raises(llm.EmptyResponse):
        llm.complete("hi", provider="qwen", api_key="key")
    assert issubclass(llm.EmptyResponse, llm.LLMError)   # 既有 except LLMError 仍能接住


def test_reasoning_only_response_is_empty_response(monkeypatch, caplog):
    body = {"choices": [{"finish_reason": "length",
                         "message": {"content": "", "reasoning_content": "我们需要…" * 50}}]}
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResponse(body))
    with pytest.raises(llm.EmptyResponse, match="空响应"):
        llm.complete("hi", provider="deepseek", api_key="key")
    assert "思考" in caplog.text     # 日志要说明是预算耗尽于思考,便于排查
