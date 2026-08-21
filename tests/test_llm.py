import os
import pytest
from src import llm


def test_complete_is_callable():
    assert callable(llm.complete)


def test_complete_raises_readable_error_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(EnvironmentError):
        llm.complete("hi")


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"), reason="需要真实 API key"
)
def test_complete_smoke():
    out = llm.complete("只回复一个字：好", system="你是测试助手")
    assert isinstance(out, str) and out.strip()
