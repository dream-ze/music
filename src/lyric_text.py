"""歌词文本的纯函数工具:音节计数、"不改字"比对、确定性切分、补结构标签。不调用 LLM。"""
import re

_CJK_CHAR = re.compile(r"[一-鿿㐀-䶿]")
_WORD = re.compile(r"[A-Za-z']+")
_TAG_LINE = re.compile(r"^\s*\[[^\]]+\]\s*$")
# 在这些标点之后切(保留标点在前半句)
_PUNCT_SPLIT = re.compile(r"(?<=[，。、；！？,.;!?])")
# 切分单元:空白 / 单个 CJK 字 / 英文单词 / 其他单字符
_UNIT = re.compile(r"\s+|[一-鿿㐀-䶿]|[A-Za-z']+|.")
_VERSE_TAG = re.compile(r"^\s*\[(Verse[^\]\-]*)\]\s*$", re.IGNORECASE)
# 这些段落通常没有人声,补标签时不分配给歌词段
_NON_VOCAL = {"intro", "outro", "instrumental"}


def _word_syllables(word: str) -> int:
    w = word.lower().strip("'")
    if not w:
        return 0
    n = max(1, len(re.findall(r"[aeiouy]+", w)))
    if len(w) > 2 and w.endswith("e") and not w.endswith("le") and n > 1:
        n -= 1
    return n


def syllables(line: str) -> int:
    """汉字 = 1;英文单词按元音组;标点/数字/空白不计。"""
    n = len(_CJK_CHAR.findall(line))
    for w in _WORD.findall(line):
        n += _word_syllables(w)
    return n


def is_tag_line(line: str) -> bool:
    return bool(_TAG_LINE.match(line))


def normalize(text: str) -> str:
    """删除所有空白与单独成行的 [标签] 行 —— "只改换行、不改字"的比对基准。"""
    kept = [ln for ln in text.splitlines() if not is_tag_line(ln)]
    return re.sub(r"\s+", "", "".join(kept))


def same_text(a: str, b: str) -> bool:
    return normalize(a) == normalize(b)


def _split_by_units(seg: str, max_s: int) -> list[str]:
    lines, cur, cur_s = [], "", 0
    for t in _UNIT.findall(seg):
        s = syllables(t)
        if cur.strip() and s and cur_s + s > max_s:
            lines.append(cur.strip())
            cur, cur_s = "", 0
        cur += t
        cur_s += s
    if cur.strip():
        lines.append(cur.strip())
    return lines


def _split_line(line: str, max_s: int) -> list[str]:
    pieces: list[str] = []
    for part in _PUNCT_SPLIT.split(line):
        if not part.strip():
            continue
        if syllables(part) <= max_s:
            pieces.append(part.strip())
        else:
            pieces.extend(_split_by_units(part, max_s))
    return pieces or [line]


def split_long_lines(text: str, max_syllables: int, tolerance: int) -> str:
    """只切不合并:超过 max+tolerance 的行先在标点处切,仍超则在空格/汉字边界切至 ≤ max。"""
    out: list[str] = []
    for ln in text.splitlines():
        if is_tag_line(ln) or syllables(ln) <= max_syllables + tolerance:
            out.append(ln)
        else:
            out.extend(_split_line(ln, max_syllables))
    return "\n".join(out)


def _qualify_verse(line: str, qualifier: str) -> str:
    m = _VERSE_TAG.match(line)
    return f"[{m.group(1).strip()} - {qualifier}]" if m else line


def apply_structure_tags(text: str, structure: list[str], vocal_qualifier: str = "") -> str:
    """用户已有标签 → 全部保留;无 → 按 structure 中的人声段顺序补;Verse 段追加限定词。"""
    lines = text.strip().splitlines()
    if any(is_tag_line(l) for l in lines):
        tagged = list(lines)
    else:
        vocal_tags = [t for t in structure if t.lower() not in _NON_VOCAL] or ["Verse"]
        sections: list[list[str]] = []
        cur: list[str] = []
        for l in lines:
            if l.strip():
                cur.append(l)
            elif cur:
                sections.append(cur)
                cur = []
        if cur:
            sections.append(cur)
        tagged = []
        for i, sec in enumerate(sections):
            if tagged:
                tagged.append("")
            tagged.append(f"[{vocal_tags[min(i, len(vocal_tags) - 1)]}]")
            tagged.extend(sec)
    if vocal_qualifier:
        tagged = [_qualify_verse(l, vocal_qualifier) for l in tagged]
    return "\n".join(tagged)
