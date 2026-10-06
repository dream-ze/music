from src.lyric_text import (
    syllables, is_tag_line, normalize, same_text, split_long_lines, apply_structure_tags,
)


# ── 音节 ──
def test_syllables_chinese_one_per_char():
    assert syllables("末班车掠过街角，雨还挂在玻璃上，") == 14   # 7 + 7,标点不计


def test_syllables_english_vowel_groups_with_silent_e():
    assert syllables("pace") == 1          # a,e → 2, 尾 e 减 1
    assert syllables("table") == 2         # 以 le 结尾不减
    assert syllables("the") == 1           # 最少 1
    assert syllables("sleepless nights") == 3


def test_syllables_mixed_line():
    # city=2(i,y) lights=1 sleepless=2 nights=1 → 6;汉字 耳机鼓点替我壮胆 = 8
    assert syllables("City lights, sleepless nights，耳机鼓点替我壮胆。") == 6 + 8


# ── 标签与比对 ──
def test_is_tag_line_only_for_whole_line_brackets():
    assert is_tag_line("[Verse - rap]") is True
    assert is_tag_line("  [Hook]  ") is True
    assert is_tag_line("我们 (together) 一起") is False


def test_normalize_drops_whitespace_and_tag_lines():
    assert normalize("[Verse]\n末班车 掠过\n街角\n\n[Hook]\nyo") == "末班车掠过街角yo"


def test_same_text_true_when_only_line_breaks_moved():
    a = "末班车掠过街角，雨还挂在玻璃上，City lights"
    b = "[Verse]\n末班车掠过街角，\n雨还挂在玻璃上，\nCity lights"
    assert same_text(a, b) is True


def test_same_text_false_when_a_char_changes():
    assert same_text("末班车掠过街角", "末班车驶过街角") is False


# ── 确定性切分 ──
def test_split_long_lines_prefers_punctuation():
    text = "末班车掠过街角，雨还挂在玻璃上，耳机鼓点替我壮胆。"   # 7+7+8 = 22 音节
    out = split_long_lines(text, max_syllables=10, tolerance=2)
    assert out.splitlines() == ["末班车掠过街角，", "雨还挂在玻璃上，", "耳机鼓点替我壮胆。"]
    assert same_text(text, out)


def test_split_long_lines_falls_back_to_char_boundary():
    text = "一二三四五六七八九十一二三四五"   # 15 音节,无标点
    out = split_long_lines(text, max_syllables=10, tolerance=2)
    assert all(syllables(l) <= 10 for l in out.splitlines())
    assert same_text(text, out)


def test_split_long_lines_keeps_short_lines_and_tags():
    text = "[Verse]\n短句\n\n[Hook]\n又一短句"
    assert split_long_lines(text, 10, 2) == text


def test_split_long_lines_english_keeps_word_spacing():
    text = "turn the pressure into bars and let the silence have its lines tonight"  # >12
    out = split_long_lines(text, 10, 2)
    assert "  " not in out and same_text(text, out)
    assert all(syllables(l) <= 10 for l in out.splitlines())


# ── 补结构标签 ──
STRUCT = ["Intro", "Verse", "Hook", "Verse", "Hook", "Outro"]


def test_apply_structure_tags_keeps_existing_tags_untouched():
    text = "[Verse]\n甲\n\n[Hook]\n乙"
    assert apply_structure_tags(text, STRUCT) == text


def test_apply_structure_tags_assigns_vocal_sections_skipping_intro_outro():
    out = apply_structure_tags("甲\n乙\n\n丙", STRUCT)
    assert out == "[Verse]\n甲\n乙\n\n[Hook]\n丙"


def test_apply_structure_tags_reuses_last_tag_when_sections_exceed():
    out = apply_structure_tags("a\n\nb\n\nc\n\nd\n\ne", STRUCT)
    assert out.split("\n\n")[-1].startswith("[Hook]")


def test_apply_structure_tags_qualifies_verse_only():
    text = "[Verse]\n甲\n\n[Verse 2]\n乙\n\n[Hook]\n丙\n\n[Verse - whispered]\n丁"
    out = apply_structure_tags(text, STRUCT, vocal_qualifier="rap")
    assert "[Verse - rap]" in out and "[Verse 2 - rap]" in out
    assert "[Hook]" in out and "[Verse - whispered]" in out   # 已有限定词与 Hook 不动


def test_section_tags_qualify_chorus_and_skip_tags_with_dash():
    text = "[Verse]\n甲\n\n[Pre-Chorus]\n乙\n\n[Chorus]\n丙\n\n[Chorus 2]\n丁"
    out = apply_structure_tags(text, STRUCT, section_tags={"Chorus": "powerful"})
    assert "[Chorus - powerful]" in out and "[Chorus 2 - powerful]" in out
    assert "[Pre-Chorus]" in out and "[Verse]\n" in out


def test_timbre_section_tags_win_over_vocal_qualifier():
    out = apply_structure_tags("[Verse]\n甲\n\n[Hook]\n乙", STRUCT,
                               vocal_qualifier="rap", section_tags={"Verse": "breathy"})
    assert "[Verse - breathy]" in out and "[Hook]" in out
