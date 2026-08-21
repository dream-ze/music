import os
from config import LLM_MODEL


def complete(prompt: str, system: str = "") -> str:
    """调用文本 LLM，返回纯文本。V0.1 唯一的 LLM 出入口。"""
    from anthropic import Anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY 未设置。请先设置环境变量再调用 LLM。"
        )
    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=LLM_MODEL,
        max_tokens=2048,
        system=system or "You are a helpful assistant.",
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(
        block.text for block in msg.content if getattr(block, "type", None) == "text"
    )
