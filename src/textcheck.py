"""文本检查:CJK 检测与 vocal_language 归一化。被 spec / planner / API 共用。"""
import re

# CJK 统一表意文字、扩展 A、CJK 标点、全角符号。caption 里出现任一即视为混入中文。
_CJK = re.compile(r"[一-鿿㐀-䶿　-〿＀-￯]")

_ZH = {"zh", "cn", "chinese", "mandarin"}
_EN = {"en", "english"}
_YUE = {"yue", "cantonese"}


def has_cjk(s: str) -> bool:
    return bool(_CJK.search(s or ""))


def normalize_language(raw: str, policy: str = "zh") -> str:
    """把 planner 可能给出的 zh-en / Chinese / mandarin 归一到 ACE-Step 合法值。

    混合(同时有中英) → policy;单一 → 对应代码;其余 → unknown。
    按 token 匹配而不是子串,否则 "french" 会因含 "en" 被判成英文。
    """
    tokens = set(re.split(r"[^a-z]+", (raw or "").lower())) - {""}
    zh, en, yue = tokens & _ZH, tokens & _EN, tokens & _YUE
    if zh and en:
        return policy
    if zh:
        return "zh"
    if en:
        return "en"
    if yue:
        return "yue"
    return "unknown"
