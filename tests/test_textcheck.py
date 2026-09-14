from src.textcheck import has_cjk, normalize_language


def test_has_cjk_detects_chinese_and_fullwidth_punct():
    assert has_cjk("中文说唱") is True
    assert has_cjk("hip hop，rap") is True      # 全角逗号也算
    assert has_cjk("hip hop, rap 808") is False
    assert has_cjk("") is False


def test_normalize_language_mixed_takes_policy():
    assert normalize_language("zh-en", policy="zh") == "zh"
    assert normalize_language("Chinese and English", policy="unknown") == "unknown"


def test_normalize_language_single_values():
    assert normalize_language("zh") == "zh"
    assert normalize_language("EN") == "en"
    assert normalize_language("cantonese") == "yue"
    assert normalize_language("yue") == "yue"


def test_normalize_language_unknown_for_others():
    assert normalize_language("french") == "unknown"   # "en" 是 french 的子串,不能误判
    assert normalize_language("") == "unknown"
    assert normalize_language("mandarin") == "zh"
