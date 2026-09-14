# Hip hop 风格 Preset 层（出歌输入链重建）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把喂给 ACE-Step 的 caption / 歌词 / 元数据重建到官方示例水准，并用数据驱动的风格 Preset 层承载 hip hop 领域知识（首批 boom bap + trap）。

**Architecture:** 新增 `src/presets.py`（Preset 数据 + 注册表）、`src/textcheck.py`（CJK 检测、语言归一化）、`src/lyric_text.py`（音节计数、逐字相等比对、确定性切分、补结构标签 —— 纯函数）；`planner` 按 preset 骨架产出英文整句 caption + keyscale + timesignature，失败回退 preset 骨架而非硬编码 mandopop；`lyrics` 改为"只断行不改字"并用逐字相等硬校验；`song_gen` 把 caption / keyscale / timesignature / `use_cot_caption` / shift 传给 ACE-Step；API 增加 `overrides.preset` 并对 CJK / 未知 preset 返回 422；前端 chips 显示中文发送英文、新增 preset 选择、灵感示例加 hip hop、降级标记显示 reason。

**Tech Stack:** Python 3 / pydantic v2 / FastAPI / pytest；Next.js 14 / TypeScript / vitest + @testing-library/react；ACE-Step 1.5（`acestep.inference.GenerationParams`）。

**Spec:** `docs/superpowers/specs/2026-09-14-hiphop-preset-layer-design.md`

## Global Constraints

- caption ≤ 512 字符（ACE-Step 上限）；planner 提示词要求 ≤ 400。
- `caption` / `genre` / `mood` / `instrument` 与 API `overrides.genre` / `overrides.mood` **不得含 CJK 字符**；CJK 判定区间：`一-鿿`、`㐀-䶿`、`　-〿`、`＀-￯`。
- `language` ∈ {`zh`, `en`, `yue`, `unknown`}；混合语言取 preset 的 `vocal_language_policy`（首批均为 `"zh"`）。
- 断行器**只可移动换行**：`normalize(输入) == normalize(输出)`，`normalize` = 删除所有空白字符与单独成行的 `[...]` 标签行。
- 断行规则默认 `min_syllables=6, max_syllables=10, tolerance=2`；汉字 = 1 音节；英文单词 = 元音组 `[aeiouy]+` 个数（最少 1），长度 > 2 且以 `e` 结尾、不以 `le` 结尾且计数 > 1 时减 1。
- 确定性切分**只切不合并**；标点（`，。、；！？,.;!?`）优先，其次空格 / CJK 字符边界。
- 结构标签：用户已有单独成行 `[...]` → 全部保留不增不删；无 → 按 preset 结构中**非** Intro/Outro/Instrumental 的标签顺序补；`Preset.vocal_qualifier` 非空时把无 `-` 限定词的 `[Verse…]` 改为 `[Verse… - <qualifier>]`，`[Hook]`/`[Chorus]` 不动。
- 降级事件：`{"stage": str, "ok": bool}`，`ok=False` 时**追加** `"reason"`；`ok=True` 时不带 `reason`（已有测试依赖）。
- 事件里不得夹带异常原文（可能含 API key）。
- shift 优先级：环境变量 `ACESTEP_SHIFT` > `preset.acestep.shift` > `3.0`；`use_cot_caption = not spec.caption_full`；`thinking=True`、`inference_steps=8` 不变。
- 校验只作用于 planner 输出与 API overrides，不回头校验已落库的旧 `spec_json`。
- 运行后端测试：`.venv/bin/python -m pytest tests/ -q`；前端：`cd web && npx vitest run`；类型：`cd web && npx tsc --noEmit`。
- 每个任务一个提交；提交信息中文，前缀 `feat:` / `fix:` / `test:` / `docs:`。
- 不提交：`.DS_Store`、`backend.log`、`findings.md`、`progress.md`、`task_plan.md`、`web/tsconfig.tsbuildinfo`、`.claude/`。

## 文件结构

| 文件 | 职责 |
|---|---|
| `src/textcheck.py`（新） | `has_cjk(s)`、`normalize_language(raw, policy)` |
| `src/presets.py`（新） | `LyricRules` / `AceStepKnobs` / `Preset` 模型，`PRESETS` 注册表，`get_preset(id)`，`Preset.render_skeleton()`、`Preset.bpm_default()` |
| `src/spec.py` | `SongSpec` 新字段 + 校验；`VALID_LANGUAGES` |
| `src/planner.py` | 注入 preset 的提示词；`skeleton_spec(preset)` 回退；带 reason 的事件 |
| `src/lyric_text.py`（新） | `syllables`、`normalize`、`same_text`、`split_long_lines`、`apply_structure_tags`、`is_tag_line` |
| `src/lyrics.py` | LLM 断行编排 + 硬校验 + 重试 + 事件 |
| `src/song_gen.py` | `build_acestep_params` 扩展、`resolve_shift`、`GenerationParams` 透传 |
| `src/pipeline.py` | preset 贯穿 |
| `server/models.py` | `Overrides.preset`；CJK / 未知 preset → 422 |
| `server/inspirations.py` | 新增 hip hop 示例（带 `preset`） |
| `web/lib/types.ts` | `overrides.preset`、Inspiration 类型 |
| `web/components/AdvancedSettings.tsx` | chips 显示中文发英文；preset 分段控件；Hip hop 默认 boom_bap |
| `web/components/GenerateForm.tsx` / `InspirationList.tsx` | preset 贯穿 |
| `web/components/SongCard.tsx` | 降级 title 显示 reason 文案 |
| `docs/superpowers/evals/hiphop-ab.md`（新） | A/B 评测记录模板与流程 |

---

### Task 1: `src/textcheck.py` — CJK 检测与语言归一化

**Files:**
- Create: `src/textcheck.py`
- Test: `tests/test_textcheck.py`

**Interfaces:**
- Produces: `has_cjk(s: str) -> bool`；`normalize_language(raw: str, policy: str = "zh") -> str`（返回值 ∈ {`zh`,`en`,`yue`,`unknown`} ∪ {policy}）。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_textcheck.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_textcheck.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.textcheck'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/textcheck.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_textcheck.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/textcheck.py tests/test_textcheck.py
git commit -m "feat: textcheck —— CJK 检测与 vocal_language 归一化"
```

---

### Task 2: `src/presets.py` — 风格 Preset 数据层

**Files:**
- Create: `src/presets.py`
- Test: `tests/test_presets.py`

**Interfaces:**
- Consumes: `src.textcheck.has_cjk`
- Produces: `class LyricRules(min_syllables:int=6, max_syllables:int=10, tolerance:int=2)`；`class AceStepKnobs(shift:float=3.0, vocal_language_policy:str="zh")`；`class Preset` 字段：`id, label, family, caption_skeleton, genre_tags:list[str], instrument_pool, texture_pool, era_pool, bpm_range:tuple[int,int], keyscale_hint, timesignature:int, structure:list[str], vocal_qualifier, vocal_gender_default, lyric_rules, acestep, examples`；方法 `render_skeleton(vocal_gender: str | None = None) -> str`、`bpm_default() -> int`；`PRESETS: dict[str, Preset]`（键 `generic`, `hiphop.boom_bap`, `hiphop.trap`）；`get_preset(preset_id: str | None) -> Preset`（空 → generic；未知 → `ValueError`）。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_presets.py
import pytest
from src.presets import PRESETS, Preset, get_preset
from src.textcheck import has_cjk


def test_registry_has_generic_and_two_hiphop_presets():
    assert set(PRESETS) == {"generic", "hiphop.boom_bap", "hiphop.trap"}


def test_get_preset_empty_returns_generic_and_unknown_raises():
    assert get_preset("").id == "generic"
    assert get_preset(None).id == "generic"
    with pytest.raises(ValueError):
        get_preset("hiphop.nope")


@pytest.mark.parametrize("pid", list(PRESETS))
def test_preset_english_fields_have_no_cjk(pid):
    p = PRESETS[pid]
    for text in [p.caption_skeleton, *p.genre_tags, *p.instrument_pool,
                 *p.texture_pool, *p.era_pool, *p.examples, p.keyscale_hint,
                 p.vocal_qualifier, p.render_skeleton()]:
        assert not has_cjk(text), text


@pytest.mark.parametrize("pid", list(PRESETS))
def test_preset_bpm_range_valid(pid):
    lo, hi = PRESETS[pid].bpm_range
    assert 40 <= lo < hi <= 200
    assert lo <= PRESETS[pid].bpm_default() <= hi


def test_hiphop_presets_use_hook_and_rap_qualifier():
    for pid in ("hiphop.boom_bap", "hiphop.trap"):
        p = PRESETS[pid]
        assert "Hook" in p.structure and "Chorus" not in p.structure
        assert p.vocal_qualifier == "rap"
        assert p.vocal_gender_default == "male"


def test_boom_bap_and_trap_bpm_ranges():
    assert PRESETS["hiphop.boom_bap"].bpm_range == (85, 95)
    assert PRESETS["hiphop.trap"].bpm_range == (130, 150)


def test_render_skeleton_fills_placeholders():
    s = PRESETS["hiphop.boom_bap"].render_skeleton()
    assert "{" not in s and "}" not in s
    assert "male rap" in s
    assert "dusty drum break" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_presets.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.presets'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/presets.py
"""风格 Preset 层:每个 preset 是一份数据,不是代码分支。新增风格只加一条数据。"""
from pydantic import BaseModel, Field


class LyricRules(BaseModel):
    min_syllables: int = 6
    max_syllables: int = 10
    tolerance: int = 2


class AceStepKnobs(BaseModel):
    shift: float = 3.0
    # 混合语言(中英)时 vocal_language 取值;A/B 时可改 "unknown"
    vocal_language_policy: str = "zh"


class Preset(BaseModel):
    id: str
    label: str
    family: str
    # 英文整句模板,占位符 {instruments} {texture} {era} {vocal}
    caption_skeleton: str
    genre_tags: list[str] = Field(default_factory=list)
    instrument_pool: list[str] = Field(default_factory=list)
    texture_pool: list[str] = Field(default_factory=list)
    era_pool: list[str] = Field(default_factory=list)
    bpm_range: tuple[int, int] = (60, 160)
    keyscale_hint: str = ""
    timesignature: int = 4
    structure: list[str]
    vocal_qualifier: str = ""
    vocal_gender_default: str = "female"
    lyric_rules: LyricRules = Field(default_factory=LyricRules)
    acestep: AceStepKnobs = Field(default_factory=AceStepKnobs)
    # 官方句式示例,注入 planner 提示词
    examples: list[str] = Field(default_factory=list)

    def render_skeleton(self, vocal_gender: str | None = None) -> str:
        """planner 降级时用的英文 caption:池中前几项填充占位符。"""
        instruments = ", ".join(self.instrument_pool[:3]) or "drums, bass, keys"
        texture = ", ".join(self.texture_pool[:2]) or "clean, balanced"
        era = self.era_pool[0] if self.era_pool else "modern"
        vocal = f"{vocal_gender or self.vocal_gender_default} {self.vocal_qualifier or 'vocal'}"
        return self.caption_skeleton.format(
            instruments=instruments, texture=texture, era=era, vocal=vocal
        )

    def bpm_default(self) -> int:
        lo, hi = self.bpm_range
        return (lo + hi) // 2


_GENERIC = Preset(
    id="generic", label="自动", family="generic",
    caption_skeleton=(
        "A {era} track featuring {instruments}, with a {texture} production "
        "and a {vocal} carrying the melody."
    ),
    genre_tags=["pop"],
    bpm_range=(60, 160),
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"],
    examples=[
        "A warm, mid-tempo pop ballad led by soft piano and airy pads, with an "
        "intimate female vocal that builds into a layered, emotive chorus."
    ],
)

_BOOM_BAP = Preset(
    id="hiphop.boom_bap", label="Boom Bap", family="hiphop",
    caption_skeleton=(
        "A {era} boom bap hip-hop track built on {instruments}. The production feels "
        "{texture}, and a confident {vocal} rides the beat with a steady, articulate flow."
    ),
    genre_tags=["hip hop", "boom bap"],
    instrument_pool=["dusty drum break", "upright bass", "jazzy piano sample",
                     "vinyl crackle", "muted trumpet stabs"],
    texture_pool=["warm", "gritty", "lo-fi"],
    era_pool=["90s", "golden era"],
    bpm_range=(85, 95),
    keyscale_hint="minor",
    structure=["Intro", "Verse", "Hook", "Verse", "Hook", "Outro"],
    vocal_qualifier="rap",
    vocal_gender_default="male",
    examples=[
        "A catchy Chinese hip-hop track with confident male rap verses, boom bap drums, "
        "and a melodic sung hook. The production features a dusty drum break, upright "
        "bass, jazzy piano samples and vinyl crackle, with a warm, gritty 90s feel.",
    ],
)

_TRAP = Preset(
    id="hiphop.trap", label="Trap", family="hiphop",
    caption_skeleton=(
        "A {era} trap track driven by {instruments}. The mix is {texture}, and an "
        "assertive {vocal} delivers tight verses over the beat with a melodic hook."
    ),
    genre_tags=["hip hop", "trap"],
    instrument_pool=["808 sub-bass", "rolling hi-hats", "trap drums",
                     "dark synth pads", "vocal chops"],
    texture_pool=["punchy", "dark", "modern"],
    era_pool=["modern", "2020s"],
    bpm_range=(130, 150),
    keyscale_hint="minor",
    structure=["Intro", "Verse", "Hook", "Verse", "Hook", "Outro"],
    vocal_qualifier="rap",
    vocal_gender_default="male",
    examples=[
        "A Chinese trap song with aggressive male rap, heavy 808s, and dark atmospheric "
        "synths. The production features hard-hitting drums, rolling hi-hats, vocal "
        "chops, and an intense energy throughout.",
    ],
)

PRESETS: dict[str, Preset] = {p.id: p for p in (_GENERIC, _BOOM_BAP, _TRAP)}


def get_preset(preset_id: str | None) -> Preset:
    """空 id → generic;未知 id 抛 ValueError(API 层转 422)。"""
    if not preset_id:
        return PRESETS["generic"]
    try:
        return PRESETS[preset_id]
    except KeyError as exc:
        raise ValueError(f"未知风格预设: {preset_id}") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_presets.py -q`
Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
git add src/presets.py tests/test_presets.py
git commit -m "feat: 风格 Preset 数据层(generic / hiphop.boom_bap / hiphop.trap)"
```

---

### Task 3: `SongSpec` 扩展与校验

**Files:**
- Modify: `src/spec.py`
- Test: `tests/test_spec.py`

**Interfaces:**
- Consumes: `src.textcheck.has_cjk`
- Produces: `SongSpec` 新字段 `caption: str = ""`, `caption_full: bool = False`, `keyscale: str = ""`, `timesignature: int | None = None`, `preset_id: str = "generic"`；常量 `VALID_LANGUAGES = {"zh","en","yue","unknown"}`；`parse_spec` 在 CJK / 非法 language / caption 超长 / 非法 timesignature 时抛 `ValueError`，CJK 错误信息包含 `"CJK"`。

- [ ] **Step 1: Write the failing test**

在 `tests/test_spec.py` 末尾追加：

```python


# ── 新字段与校验 ────────────────────────────────────────────────────

def test_new_fields_have_defaults_for_old_spec_json():
    """旧 spec_json 没有新字段也要能解析。"""
    spec = parse_spec(dict(SAFE_DEFAULT_SPEC))
    assert spec.caption == "" and spec.caption_full is False
    assert spec.keyscale == "" and spec.timesignature is None
    assert spec.preset_id == "generic"


def test_caption_with_cjk_rejected():
    data = dict(SAFE_DEFAULT_SPEC, caption="A hip hop track 中文说唱")
    with pytest.raises(ValueError, match="CJK"):
        parse_spec(data)


def test_genre_mood_instrument_with_cjk_rejected():
    for field in ("genre", "mood", "instrument"):
        data = dict(SAFE_DEFAULT_SPEC)
        data[field] = ["hip hop", "夜晚"]
        with pytest.raises(ValueError, match="CJK"):
            parse_spec(data)


def test_language_must_be_valid():
    with pytest.raises(ValueError):
        parse_spec(dict(SAFE_DEFAULT_SPEC, language="zh-en"))
    assert parse_spec(dict(SAFE_DEFAULT_SPEC, language="unknown")).language == "unknown"


def test_caption_max_512_chars():
    with pytest.raises(ValueError):
        parse_spec(dict(SAFE_DEFAULT_SPEC, caption="a" * 513))
    assert len(parse_spec(dict(SAFE_DEFAULT_SPEC, caption="a" * 512)).caption) == 512


def test_timesignature_enum():
    assert parse_spec(dict(SAFE_DEFAULT_SPEC, timesignature=4)).timesignature == 4
    with pytest.raises(ValueError):
        parse_spec(dict(SAFE_DEFAULT_SPEC, timesignature=5))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_spec.py -q`
Expected: 6 failed（`AttributeError: 'SongSpec' object has no attribute 'caption'` / `DID NOT RAISE`）

- [ ] **Step 3: Write minimal implementation**

把 `src/spec.py` 整体替换为：

```python
from pydantic import BaseModel, Field, ValidationError, field_validator

from src.textcheck import has_cjk

# ACE-Step VALID_LANGUAGES 中本项目支持的子集(其余一律归一为 unknown)
VALID_LANGUAGES = {"zh", "en", "yue", "unknown"}
_VALID_TIMESIGNATURES = {2, 3, 4, 6}


class VocalSpec(BaseModel):
    gender: str = "female"
    style: str = "soft"


class SongSpec(BaseModel):
    language: str = "zh"
    vocal: VocalSpec = Field(default_factory=VocalSpec)
    genre: list[str] = Field(default_factory=lambda: ["mandopop"])
    mood: list[str] = Field(default_factory=lambda: ["warm"])
    instrument: list[str] = Field(default_factory=lambda: ["piano", "soft drums"])
    bpm: int = Field(default=90, ge=40, le=200)
    structure: list[str] = Field(
        default_factory=lambda: ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"]
    )
    # ── 2026-09 输入链重建新增(均有默认值,兼容旧 spec_json) ──
    caption: str = ""            # 英文整句;空表示回退到标签串
    caption_full: bool = False   # caption 是否为 planner 产出的完整整句 → 决定 use_cot_caption
    keyscale: str = ""           # 如 "F minor";空交给 LM
    timesignature: int | None = None
    preset_id: str = "generic"

    @field_validator("caption", "genre", "mood", "instrument")
    @classmethod
    def _no_cjk(cls, v):
        items = v if isinstance(v, list) else [v]
        if any(has_cjk(x) for x in items):
            raise ValueError("must not contain CJK characters")
        return v

    @field_validator("caption")
    @classmethod
    def _caption_len(cls, v: str) -> str:
        if len(v) > 512:
            raise ValueError("caption longer than 512 chars")
        return v

    @field_validator("language")
    @classmethod
    def _language(cls, v: str) -> str:
        if v not in VALID_LANGUAGES:
            raise ValueError(f"language must be one of {sorted(VALID_LANGUAGES)}")
        return v

    @field_validator("timesignature")
    @classmethod
    def _timesig(cls, v):
        if v is not None and v not in _VALID_TIMESIGNATURES:
            raise ValueError("timesignature must be 2/3/4/6")
        return v


SAFE_DEFAULT_SPEC: dict = {
    "language": "zh",
    "vocal": {"gender": "female", "style": "soft"},
    "genre": ["mandopop"],
    "mood": ["warm"],
    "instrument": ["piano", "soft drums"],
    "bpm": 90,
    "structure": ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"],
}


def parse_spec(data: dict) -> SongSpec:
    try:
        return SongSpec(**data)
    except ValidationError as e:
        raise ValueError(str(e)) from e


def safe_spec() -> SongSpec:
    """测试与兼容用的通用 spec。planner 降级不再用它,而是用 preset 骨架。"""
    return SongSpec(**SAFE_DEFAULT_SPEC)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_spec.py tests/test_planner.py tests/test_pipeline.py -q`
Expected: 全部 PASS（旧测试不受影响）

- [ ] **Step 5: Commit**

```bash
git add src/spec.py tests/test_spec.py
git commit -m "feat: SongSpec 增加 caption/keyscale/timesignature/preset_id 与 CJK、语言校验"
```

---

### Task 4: `src/lyric_text.py` — 音节、逐字比对、确定性切分、补标签

**Files:**
- Create: `src/lyric_text.py`
- Test: `tests/test_lyric_text.py`
- Modify: `docs/superpowers/specs/2026-09-14-hiphop-preset-layer-design.md` §5.5（补一句：无标签歌词补标签时跳过 Intro/Outro/Instrumental）

**Interfaces:**
- Produces: `syllables(line: str) -> int`；`is_tag_line(line: str) -> bool`；`normalize(text: str) -> str`；`same_text(a: str, b: str) -> bool`；`split_long_lines(text: str, max_syllables: int, tolerance: int) -> str`；`apply_structure_tags(text: str, structure: list[str], vocal_qualifier: str = "") -> str`。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lyric_text.py
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
    # city=2(i,y) lights=1 sleepless=2 nights=1 → 6;汉字 7
    assert syllables("City lights, sleepless nights，耳机鼓点替我壮胆。") == 6 + 7


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_lyric_text.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.lyric_text'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/lyric_text.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_lyric_text.py -q`
Expected: `16 passed`

- [ ] **Step 5: 同步 spec 措辞**

在 `docs/superpowers/specs/2026-09-14-hiphop-preset-layer-design.md` §5.5「结构标签」第二条末尾追加：`；分配时跳过 Intro / Outro / Instrumental（通常无人声）`。

- [ ] **Step 6: Commit**

```bash
git add src/lyric_text.py tests/test_lyric_text.py docs/superpowers/specs/2026-09-14-hiphop-preset-layer-design.md
git commit -m "feat: lyric_text —— 音节计数、逐字比对、确定性切分、补结构标签"
```

---

### Task 5: `src/lyrics.py` — 只断行不改字的 LLM 编排

**Files:**
- Modify: `src/lyrics.py`（整体替换）
- Test: `tests/test_lyrics.py`（更新旧断言 + 新增）

**Interfaces:**
- Consumes: `src.lyric_text.{same_text, split_long_lines, apply_structure_tags}`；`src.presets.{Preset, get_preset}`；`SongSpec.structure`、`SongSpec.preset_id`。
- Produces: `structure_lyrics(raw_lyrics: str, spec: SongSpec, *, preset: Preset | None = None, llm_options: dict | None = None, status_events: list[dict] | None = None) -> str`；事件 `{"stage": "歌词整理", "ok": True}` 或 `{"stage": "歌词整理", "ok": False, "reason": "llm_error" | "empty" | "text_changed"}`。

- [ ] **Step 1: 更新旧测试并写新失败测试**

把 `tests/test_lyrics.py` 整体替换为：

```python
import json
from src import lyrics
from src.presets import get_preset
from src.spec import safe_spec

_TAGGED = """[Verse]
末班车掠过街角
City lights, sleepless nights

[Hook]
一拍一拍，把沉默拆开
Turn it up, feel the bass"""


def test_llm_output_accepted_when_only_line_breaks_moved(monkeypatch):
    raw = "末班车掠过街角，雨还挂在玻璃上，耳机鼓点替我壮胆"
    monkeypatch.setattr(lyrics.llm, "complete",
                        lambda *a, **k: "末班车掠过街角，\n雨还挂在玻璃上，\n耳机鼓点替我壮胆")
    events = []
    out = lyrics.structure_lyrics(raw, safe_spec(), status_events=events)
    assert out.splitlines()[1:] == ["末班车掠过街角，", "雨还挂在玻璃上，", "耳机鼓点替我壮胆"]
    assert out.startswith("[Verse]")           # 无标签 → 按结构补
    assert events == [{"stage": "歌词整理", "ok": True}]


def test_llm_output_rejected_when_text_changed(monkeypatch):
    raw = "末班车掠过街角，雨还挂在玻璃上"
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "末班车驶过街角，\n雨还挂在玻璃上")
    events = []
    out = lyrics.structure_lyrics(raw, safe_spec(), status_events=events)
    assert "驶过" not in out and "掠过" in out   # 丢弃 LLM 输出
    assert events == [{"stage": "歌词整理", "ok": False, "reason": "text_changed"}]


def test_empty_response_retries_once_then_falls_back(monkeypatch):
    calls = []
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: calls.append(1) or "   ")
    events = []
    out = lyrics.structure_lyrics("第一句\n第二句", safe_spec(), status_events=events)
    assert len(calls) == 2
    assert "第一句" in out and "[Verse]" in out
    assert events == [{"stage": "歌词整理", "ok": False, "reason": "empty"}]


def test_exception_falls_back_without_leaking_secret(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network down, key=super-secret")
    monkeypatch.setattr(lyrics.llm, "complete", boom)
    events = []
    out = lyrics.structure_lyrics("歌词", safe_spec(),
                                  llm_options={"provider": "openai"}, status_events=events)
    assert "歌词" in out
    assert events == [{"stage": "歌词整理", "ok": False, "reason": "llm_error"}]
    assert "super-secret" not in json.dumps(events, ensure_ascii=False)


def test_fallback_splits_long_lines_deterministically(monkeypatch):
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "")
    raw = "末班车掠过街角，雨还挂在玻璃上，耳机鼓点替我壮胆。"
    out = lyrics.structure_lyrics(raw, safe_spec())
    body = [l for l in out.splitlines() if l and not l.startswith("[")]
    assert body == ["末班车掠过街角，", "雨还挂在玻璃上，", "耳机鼓点替我壮胆。"]


def test_tagged_lyrics_keep_tags_and_never_duplicate(monkeypatch):
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "")
    out = lyrics.structure_lyrics(_TAGGED, safe_spec())
    assert out.count("[Verse]") == 1 and out.count("[Hook]") == 1
    assert "[Chorus]" not in out
    assert out.count("末班车掠过街角") == 1


def test_untagged_lyrics_no_longer_duplicated_into_chorus(monkeypatch):
    """旧行为把整段复制成 [Chorus];新行为按结构补标签,不复制。"""
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "")
    out = lyrics.structure_lyrics("第一句\n第二句", safe_spec())
    assert out.count("第一句") == 1 and out.startswith("[Verse]")


def test_hiphop_preset_qualifies_verse_with_rap(monkeypatch):
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "")
    spec = safe_spec()
    out = lyrics.structure_lyrics(_TAGGED, spec, preset=get_preset("hiphop.boom_bap"))
    assert "[Verse - rap]" in out and "[Hook]" in out


def test_prompt_contains_rules_and_forbids_edits(monkeypatch):
    seen = {}
    monkeypatch.setattr(lyrics.llm, "complete",
                        lambda prompt, **k: seen.update(prompt=prompt, system=k.get("system")) or "")
    lyrics.structure_lyrics("x", safe_spec(), preset=get_preset("hiphop.trap"))
    assert "6-10" in seen["prompt"] and "不改字" in seen["prompt"]
    assert "只能移动换行" in seen["system"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_lyrics.py -q`
Expected: 多数 FAIL（`TypeError: structure_lyrics() got an unexpected keyword argument 'preset'`、事件缺 `reason`、`[Chorus]` 仍出现）

- [ ] **Step 3: Write minimal implementation**

把 `src/lyrics.py` 整体替换为：

```python
"""歌词整理:只调整换行、不改字。LLM 负责断行,确定性校验兜底。"""
import logging

from src import llm
from src.lyric_text import apply_structure_tags, same_text, split_long_lines
from src.presets import Preset, get_preset
from src.spec import SongSpec

_SYSTEM = (
    "你是作词编辑。你的唯一任务是调整歌词的换行位置。"
    "绝对不可以增加、删除或修改任何一个字、标点或英文单词;只能移动换行。"
    "保留所有单独成行的 [标签] 行和段落之间的空行。只输出歌词文本,不要解释。"
)

_TEMPLATE = """断行规则:
- 每行 {min_s}-{max_s} 个音节(一个汉字算 1 个音节,英文按单词音节数)
- 同一段里位置相同的行音节数尽量接近(相差不超过 {tol})
- 不改字、不改标点、不改顺序;只移动换行
- 已有的 [标签] 行和段间空行原样保留

歌词:
{lyrics}"""


def _ask(text: str, preset: Preset, llm_options: dict | None) -> str:
    r = preset.lyric_rules
    prompt = _TEMPLATE.format(min_s=r.min_syllables, max_s=r.max_syllables,
                              tol=r.tolerance, lyrics=text)
    return llm.complete(prompt, system=_SYSTEM, **(llm_options or {})) or ""


def _emit(events: list[dict] | None, ok: bool, reason: str | None) -> None:
    if events is None:
        return
    ev: dict = {"stage": "歌词整理", "ok": ok}
    if not ok:
        ev["reason"] = reason
    events.append(ev)


def structure_lyrics(
    raw_lyrics: str,
    spec: SongSpec,
    *,
    preset: Preset | None = None,
    llm_options: dict | None = None,
    status_events: list[dict] | None = None,
) -> str:
    preset = preset or get_preset(spec.preset_id)
    rules = preset.lyric_rules
    base = raw_lyrics.strip() or "……"

    ok, reason, text = True, None, None
    try:
        out = _ask(base, preset, llm_options)
        if not out.strip():
            out = _ask(base, preset, llm_options)  # 空响应重试一次
        if not out.strip():
            ok, reason = False, "empty"
        elif not same_text(base, out):
            ok, reason = False, "text_changed"    # LLM 改了字:整份丢弃
        else:
            text = out.strip()
    except Exception as e:  # noqa: BLE001 — 事件里不带异常原文(可能含 key)
        logging.warning("lyrics LLM failed, using deterministic split: %s", e)
        ok, reason = False, "llm_error"

    if text is None:
        text = base
    # 无论 LLM 路径还是回退,都再做一次确定性切分:对合规文本是幂等的
    text = split_long_lines(text, rules.max_syllables, rules.tolerance)
    text = apply_structure_tags(text, spec.structure or preset.structure, preset.vocal_qualifier)
    _emit(status_events, ok, reason)
    return text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_lyrics.py tests/test_lyric_text.py -q`
Expected: 全部 PASS。（`tests/test_pipeline.py` 此时会因事件多了 `reason` 而失败 —— Task 7 修。）

- [ ] **Step 5: Commit**

```bash
git add src/lyrics.py tests/test_lyrics.py
git commit -m "feat: 歌词整理改为只断行不改字(逐字相等硬校验 + 确定性回退 + reason 事件)"
```

---

### Task 6: `src/planner.py` — 注入 preset、骨架回退、reason 事件

**Files:**
- Modify: `src/planner.py`（整体替换）
- Test: `tests/test_planner.py`（更新 + 新增）

**Interfaces:**
- Consumes: `src.presets.{Preset, get_preset}`；`src.textcheck.normalize_language`；`src.spec.{SongSpec, VocalSpec, parse_spec}`。
- Produces: `plan_song(style_desc: str, lyrics_hint: str = "", *, preset: Preset | None = None, llm_options: dict | None = None, status_events: list[dict] | None = None) -> SongSpec`；`skeleton_spec(preset: Preset) -> SongSpec`；事件 `{"stage": "歌曲规划", "ok": True}` 或 `{"stage": "歌曲规划", "ok": False, "reason": "llm_error" | "bad_json" | "non_english" | "invalid_spec"}`。

- [ ] **Step 1: 更新旧测试并写新失败测试**

把 `tests/test_planner.py` 整体替换为：

```python
import json
from src import planner
from src.presets import get_preset
from src.spec import SongSpec

GOOD = {
    "language": "zh",
    "vocal": {"gender": "male", "style": "laid-back rap"},
    "genre": ["hip hop", "boom bap"],
    "mood": ["nocturnal", "introspective"],
    "instrument": ["dusty drum break", "upright bass", "vinyl crackle"],
    "bpm": 90,
    "keyscale": "F minor",
    "timesignature": 4,
    "structure": ["Intro", "Verse", "Hook", "Verse", "Hook", "Outro"],
    "caption": "A warm 90s boom bap hip-hop track with a confident male rap over a dusty "
               "drum break, upright bass and vinyl crackle.",
}


def test_plan_song_parses_llm_json_and_marks_caption_full(monkeypatch):
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: json.dumps(GOOD))
    events = []
    spec = planner.plan_song("hip hop 说唱", preset=get_preset("hiphop.boom_bap"),
                             status_events=events)
    assert isinstance(spec, SongSpec)
    assert spec.bpm == 90 and spec.keyscale == "F minor" and spec.timesignature == 4
    assert spec.caption_full is True and spec.preset_id == "hiphop.boom_bap"
    assert events == [{"stage": "歌曲规划", "ok": True}]


def test_plan_song_json_in_code_fence(monkeypatch):
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: f"```json\n{json.dumps(GOOD)}\n```")
    assert planner.plan_song("随便").bpm == 90


def test_plan_song_normalizes_mixed_language_to_policy(monkeypatch):
    monkeypatch.setattr(planner.llm, "complete",
                        lambda *a, **k: json.dumps(dict(GOOD, language="zh-en")))
    spec = planner.plan_song("中英混合", preset=get_preset("hiphop.trap"))
    assert spec.language == "zh"


def test_plan_song_cjk_in_output_falls_back_to_skeleton(monkeypatch):
    bad = dict(GOOD, genre=["hip hop", "中文说唱"], instrument=["鼓机", "贝斯"])
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: json.dumps(bad))
    events = []
    spec = planner.plan_song("说唱", preset=get_preset("hiphop.boom_bap"), status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "non_english"}]
    assert spec.preset_id == "hiphop.boom_bap" and spec.caption_full is False
    assert "boom bap" in spec.caption and spec.bpm == 90       # 骨架:区间中点
    assert spec.vocal.gender == "male" and "Hook" in spec.structure


def test_plan_song_garbage_falls_back_with_bad_json(monkeypatch):
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: "抱歉我不会")
    events = []
    spec = planner.plan_song("女声", status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "bad_json"}]
    assert spec.preset_id == "generic" and spec.caption          # generic 骨架也有英文 caption


def test_plan_song_exception_falls_back_with_llm_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(planner.llm, "complete", boom)
    events = []
    spec = planner.plan_song("女声", status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "llm_error"}]
    assert spec.language == "zh"


def test_plan_song_invalid_spec_reason(monkeypatch):
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: json.dumps(dict(GOOD, bpm=999)))
    events = []
    planner.plan_song("随便", status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "invalid_spec"}]


def test_plan_song_passes_llm_options(monkeypatch):
    captured = {}
    monkeypatch.setattr(planner.llm, "complete",
                        lambda *a, **k: captured.update(k) or json.dumps(GOOD))
    planner.plan_song("温柔", llm_options={"provider": "deepseek", "model": "custom", "api_key": "k"})
    assert captured["provider"] == "deepseek" and captured["model"] == "custom"


def test_prompt_injects_preset_skeleton_examples_and_bpm_range(monkeypatch):
    seen = {}
    monkeypatch.setattr(planner.llm, "complete",
                        lambda prompt, **k: seen.update(prompt=prompt) or json.dumps(GOOD))
    planner.plan_song("说唱", preset=get_preset("hiphop.trap"))
    p = seen["prompt"]
    assert "130-150" in p and "808 sub-bass" in p and "Trap" in p
    assert "Chinese trap song" in p            # 官方示例句
    assert "不得出现中文" in p


def test_skeleton_spec_is_valid_and_english():
    spec = planner.skeleton_spec(get_preset("hiphop.trap"))
    assert spec.bpm == 140 and spec.timesignature == 4 and spec.genre == ["hip hop", "trap"]
    assert spec.caption and spec.caption_full is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_planner.py -q`
Expected: 多数 FAIL（`unexpected keyword argument 'preset'`、`AttributeError: module 'src.planner' has no attribute 'skeleton_spec'`）

- [ ] **Step 3: Write minimal implementation**

把 `src/planner.py` 整体替换为：

```python
import json
import logging
import re

from src import llm
from src.presets import Preset, get_preset
from src.spec import SongSpec, VocalSpec, parse_spec
from src.textcheck import normalize_language

_SYSTEM = (
    "你是音乐制作人。根据用户对歌曲感觉的描述和给定的风格预设,只输出一个 JSON 对象,不要多余文字。"
    "caption 与所有英文字段必须是英文,不得出现中文。"
)

_TEMPLATE = """用户想要的感觉:{style}
{hint}
风格预设:{label}
- caption 句式骨架(英文;可改写,但须保持自然语言整句):{skeleton}
- 可选乐器词:{instruments}
- 可选质感词:{textures}
- 可选年代/制作词:{eras}
- BPM 范围:{bpm_lo}-{bpm_hi}
- 调性倾向:{keyscale_hint}
- 结构模板:{structure}
- 官方风格 caption 示例(学习句式与维度,不要照抄):
{examples}

请输出 JSON,字段:
language(zh/en/yue/unknown), vocal{{gender, style}}, genre(英文数组), mood(英文数组),
instrument(英文数组), bpm(整数,在范围内), keyscale(如 "F minor"), timesignature(2/3/4/6),
structure(数组), caption(1-3 句英文,尽量覆盖 风格/情绪/乐器/质感/年代/制作/人声/速度/结构 九个维度,
不超过 400 字符)。所有字段不得出现中文。只输出 JSON。"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no json object in llm output")
    return json.loads(m.group(0))


def _emit(events: list[dict] | None, ok: bool, reason: str | None) -> None:
    if events is None:
        return
    ev: dict = {"stage": "歌曲规划", "ok": ok}
    if not ok:
        ev["reason"] = reason
    events.append(ev)


def skeleton_spec(preset: Preset) -> SongSpec:
    """planner 降级时的 spec:用 preset 的英文骨架,而不是硬编码的 mandopop 模板。"""
    return SongSpec(
        language=preset.acestep.vocal_language_policy,
        vocal=VocalSpec(gender=preset.vocal_gender_default,
                        style=preset.vocal_qualifier or "soft"),
        genre=list(preset.genre_tags) or ["pop"],
        mood=["neutral"],
        instrument=list(preset.instrument_pool[:3]) or ["drums", "bass", "keys"],
        bpm=preset.bpm_default(),
        structure=list(preset.structure),
        caption=preset.render_skeleton(),
        caption_full=False,
        keyscale="",
        timesignature=preset.timesignature,
        preset_id=preset.id,
    )


def _build_prompt(style_desc: str, lyrics_hint: str, preset: Preset) -> str:
    hint = f"歌词片段参考:{lyrics_hint}" if lyrics_hint else ""
    return _TEMPLATE.format(
        style=style_desc, hint=hint, label=preset.label,
        skeleton=preset.caption_skeleton,
        instruments=", ".join(preset.instrument_pool) or "(不限)",
        textures=", ".join(preset.texture_pool) or "(不限)",
        eras=", ".join(preset.era_pool) or "(不限)",
        bpm_lo=preset.bpm_range[0], bpm_hi=preset.bpm_range[1],
        keyscale_hint=preset.keyscale_hint or "(不限)",
        structure=" / ".join(preset.structure),
        examples="\n".join(f"  - {e}" for e in preset.examples) or "  (无)",
    )


def plan_song(
    style_desc: str,
    lyrics_hint: str = "",
    *,
    preset: Preset | None = None,
    llm_options: dict | None = None,
    status_events: list[dict] | None = None,
) -> SongSpec:
    preset = preset or get_preset("")
    prompt = _build_prompt(style_desc, lyrics_hint, preset)
    reason: str | None
    try:
        raw = llm.complete(prompt, system=_SYSTEM, **(llm_options or {}))
    except Exception as e:  # noqa: BLE001 — 事件里不带异常原文
        logging.warning("planner LLM failed, using preset skeleton: %s", e)
        reason = "llm_error"
    else:
        try:
            data = _extract_json(raw)
        except (ValueError, json.JSONDecodeError):
            reason = "bad_json"
        else:
            data["language"] = normalize_language(
                str(data.get("language", "")), preset.acestep.vocal_language_policy
            )
            data["preset_id"] = preset.id
            data["caption_full"] = bool(str(data.get("caption", "")).strip())
            try:
                spec = parse_spec(data)
            except ValueError as e:
                reason = "non_english" if "CJK" in str(e) else "invalid_spec"
                logging.warning("planner output rejected (%s), using preset skeleton", reason)
            else:
                _emit(status_events, True, None)
                return spec
    _emit(status_events, False, reason)
    return skeleton_spec(preset)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_planner.py tests/test_spec.py tests/test_presets.py -q`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add src/planner.py tests/test_planner.py
git commit -m "feat: planner 注入风格 preset,产出英文整句 caption/keyscale/timesignature,降级回退 preset 骨架"
```

---

### Task 7: `src/pipeline.py` — preset 贯穿与事件汇总

**Files:**
- Modify: `src/pipeline.py`
- Test: `tests/test_pipeline.py`（更新事件断言 + 新增）

**Interfaces:**
- Consumes: `planner.plan_song(..., preset=)`、`lyrics.structure_lyrics(..., preset=)`、`presets.get_preset`。
- Produces: `make_song(..., overrides={"preset": "hiphop.trap", ...})`；返回 dict 新增 `"preset_id": str`；`llm_status` 事件带 `reason`；`degraded` 不变。

- [ ] **Step 1: 更新旧断言并写新失败测试**

在 `tests/test_pipeline.py` 中：

(a) 把 `test_make_song_propagates_llm_options_and_keeps_generating_on_fallback` 的断言

```python
    assert result["llm_status"] == [
        {"stage": "歌曲规划", "ok": False}, {"stage": "歌词整理", "ok": False}
    ]
```
改为
```python
    assert result["llm_status"] == [
        {"stage": "歌曲规划", "ok": False, "reason": "llm_error"},
        {"stage": "歌词整理", "ok": False, "reason": "llm_error"},
    ]
```

(b) 在 `test_make_song_orchestrates` 的 `fake_complete` 中，planner 分支返回的 `SAFE_DEFAULT_SPEC` 保持；歌词分支返回 `"[Verse]\nx\n[Chorus]\ny"` 而输入是 `"我的歌词"` —— 新断行器会因 `text_changed` 拒绝。把该测试的歌词分支改为返回原词 `"我的歌词"`，并把断言 `assert "[Verse]" in result["structured_lyrics"]` 保留（无标签 → 自动补 `[Verse]`）。

(c) 文件末尾追加：

```python


def test_make_song_threads_preset_to_planner_and_lyrics(monkeypatch, tmp_path):
    seen = {}

    def fake_plan(style, lyrics_hint="", *, preset=None, llm_options=None, status_events=None):
        seen["plan_preset"] = preset.id
        status_events.append({"stage": "歌曲规划", "ok": True})
        return pipeline.planner.skeleton_spec(preset)

    def fake_lyrics(raw, spec, *, preset=None, llm_options=None, status_events=None):
        seen["lyrics_preset"] = preset.id
        status_events.append({"stage": "歌词整理", "ok": True})
        return "[Verse - rap]\n" + raw

    monkeypatch.setattr(pipeline.planner, "plan_song", fake_plan)
    monkeypatch.setattr(pipeline.lyrics, "structure_lyrics", fake_lyrics)
    monkeypatch.setattr(pipeline.song_gen, "generate_song",
                        lambda structured, spec, **k: k["out_path"])

    result = pipeline.make_song("词", "说唱", work_dir=str(tmp_path),
                                overrides={"preset": "hiphop.trap"})
    assert seen == {"plan_preset": "hiphop.trap", "lyrics_preset": "hiphop.trap"}
    assert result["preset_id"] == "hiphop.trap"
    assert result["spec"].preset_id == "hiphop.trap"
    assert result["degraded"] is False


def test_make_song_unknown_preset_raises(monkeypatch, tmp_path):
    import pytest
    with pytest.raises(ValueError):
        pipeline.make_song("词", "x", work_dir=str(tmp_path), overrides={"preset": "nope"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_pipeline.py -q`
Expected: FAIL（`KeyError: 'preset_id'`、事件缺 `reason`、`unexpected keyword argument 'preset'`）

- [ ] **Step 3: Write minimal implementation**

把 `src/pipeline.py` 中 `make_song` 替换为：

```python
def make_song(raw_lyrics: str, style_desc: str, *,
              length: str = "full", seed: int | None = None,
              work_dir: str | None = None,
              overrides: dict | None = None,
              llm_options: dict | None = None) -> dict:
    out_dir = work_dir or config.OUTPUTS_DIR
    os.makedirs(out_dir, exist_ok=True)
    overrides = overrides or {}

    # 风格预设只由 UI 选择;未选 → generic。未知 id 在 API 层已被 422 拦下,这里抛错兜底。
    preset = get_preset(overrides.get("preset"))

    # 调用方没指定供应商时用配置值(而不是 llm.complete 签名里的默认值)。
    llm_options = {"provider": config.LLM_PROVIDER, **(llm_options or {})}

    llm_status: list[dict] = []
    spec = planner.plan_song(
        style_desc, lyrics_hint=raw_lyrics[:80], preset=preset,
        llm_options=llm_options, status_events=llm_status,
    )
    if overrides:
        spec = _apply_overrides(spec, overrides)
    structured = lyrics.structure_lyrics(
        raw_lyrics, spec, preset=preset, llm_options=llm_options, status_events=llm_status
    )
    song_path = os.path.join(out_dir, "song.wav")
    song_path = song_gen.generate_song(
        structured, spec, length=length, seed=seed, out_path=song_path
    )
    return {
        "spec": spec,
        "structured_lyrics": structured,
        "song": song_path,
        "preset_id": preset.id,
        "llm_status": llm_status,
        # 任一阶段回退即为降级生成 —— 由事件的 ok 位判定,不靠文案匹配。
        "degraded": any(not e["ok"] for e in llm_status),
    }
```

并在文件顶部 `from src import planner, lyrics, song_gen` 之后加一行：`from src.presets import get_preset`。

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 全部 PASS（此时 `test_queue.py` 的假 `make_song` 不含 `preset_id`，`queue` 尚未读它，不受影响）

- [ ] **Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline 贯穿风格 preset,事件携带 reason"
```

---

### Task 8: `src/song_gen.py` — caption / keyscale / timesignature / use_cot_caption / shift 透传

**Files:**
- Modify: `src/song_gen.py`
- Test: `tests/test_song_gen.py`

**Interfaces:**
- Consumes: `SongSpec.{caption, caption_full, keyscale, timesignature, preset_id, language}`；`presets.get_preset`。
- Produces: `build_acestep_params(spec, length="full", seed=None) -> dict` 新增键 `caption`（= `spec.caption` 或标签串）、`keyscale`、`timesignature`（str，空为 `""`）、`use_cot_caption`（bool）、`shift`（float）；保留 `prompt`（与 `caption` 相同）；`resolve_shift(preset_id: str) -> float`。

- [ ] **Step 1: Write the failing test**

在 `tests/test_song_gen.py` 末尾追加：

```python


# ── caption / keyscale / timesignature / use_cot_caption / shift 透传 ──

def _hiphop_spec(**over):
    from src.spec import SongSpec, VocalSpec
    base = dict(language="zh", vocal=VocalSpec(gender="male", style="rap"),
                genre=["hip hop"], mood=["dark"], instrument=["808 sub-bass"], bpm=140,
                structure=["Verse", "Hook"], caption="A dark trap track with male rap.",
                caption_full=True, keyscale="G minor", timesignature=4, preset_id="hiphop.trap")
    base.update(over)
    return SongSpec(**base)


def test_params_use_full_caption_and_disable_cot_caption():
    p = build_acestep_params(_hiphop_spec())
    assert p["caption"] == "A dark trap track with male rap."
    assert p["prompt"] == p["caption"]
    assert p["use_cot_caption"] is False


def test_params_fall_back_to_tag_string_and_enable_cot_caption():
    p = build_acestep_params(_hiphop_spec(caption="", caption_full=False))
    assert "hip hop" in p["caption"] and "808 sub-bass" in p["caption"]
    assert p["use_cot_caption"] is True


def test_params_pass_keyscale_and_timesignature_as_strings():
    p = build_acestep_params(_hiphop_spec())
    assert p["keyscale"] == "G minor" and p["timesignature"] == "4"
    q = build_acestep_params(_hiphop_spec(keyscale="", timesignature=None))
    assert q["keyscale"] == "" and q["timesignature"] == ""


def test_shift_priority_env_over_preset_over_default(monkeypatch):
    monkeypatch.delenv("ACESTEP_SHIFT", raising=False)
    assert song_gen.resolve_shift("hiphop.trap") == 3.0        # preset 默认 3.0
    monkeypatch.setenv("ACESTEP_SHIFT", "1.5")
    assert song_gen.resolve_shift("hiphop.trap") == 1.5
    assert build_acestep_params(_hiphop_spec())["shift"] == 1.5


def test_generate_song_forwards_new_params(fake_acestep, monkeypatch, tmp_path):
    """GenerationParams 必须拿到 caption/keyscale/timesignature/use_cot_caption/shift。"""
    import types as _t
    captured = {}

    class _GP:
        def __init__(self, **kw):
            captured.update(kw)

    class _GC:
        def __init__(self, **kw):
            pass

    def _gen(dit, llm, params, cfg, save_dir):
        return _t.SimpleNamespace(success=True, audios=[{"path": str(tmp_path / "o.wav")}], error=None)

    inf = _t.ModuleType("acestep.inference")
    inf.GenerationParams, inf.GenerationConfig, inf.generate_music = _GP, _GC, _gen
    monkeypatch.setitem(sys.modules, "acestep.inference", inf)
    fake_acestep()
    monkeypatch.delenv("ZE_FAKE_GEN", raising=False)
    monkeypatch.delenv("ACESTEP_SHIFT", raising=False)

    song_gen.generate_song("[Verse - rap]\nyo", _hiphop_spec(), length="short",
                           out_path=str(tmp_path / "o.wav"))
    assert captured["caption"] == "A dark trap track with male rap."
    assert captured["keyscale"] == "G minor" and captured["timesignature"] == "4"
    assert captured["use_cot_caption"] is False and captured["vocal_language"] == "zh"
    assert captured["shift"] == 3.0 and captured["thinking"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_song_gen.py -q`
Expected: FAIL（`KeyError: 'caption'`、`AttributeError: ... no attribute 'resolve_shift'`）

- [ ] **Step 3: Write minimal implementation**

在 `src/song_gen.py` 中：

(a) 顶部 `from src.spec import SongSpec` 之后加：`from src.presets import get_preset`。

(b) 把 `_SHIFT = 3.0` 与其注释替换为：

```python
# turbo 模型推荐 shift=3.0(官方评价:语义强、清晰,但偏"干"、配器极简)。
# 优先级:环境变量 ACESTEP_SHIFT > preset.acestep.shift > 3.0,便于不改代码做 A/B。
_DEFAULT_SHIFT = 3.0


def resolve_shift(preset_id: str) -> float:
    env = os.environ.get("ACESTEP_SHIFT", "").strip()
    if env:
        return float(env)
    try:
        return float(get_preset(preset_id).acestep.shift)
    except ValueError:
        return _DEFAULT_SHIFT
```

(c) 把 `build_acestep_params` 替换为：

```python
def build_acestep_params(spec: SongSpec, length: str = "full", seed: int | None = None) -> dict:
    tags = [*spec.genre, *spec.mood, *spec.instrument,
            f"{spec.vocal.gender} vocal", spec.vocal.style]
    tag_string = ", ".join(t for t in tags if t)
    # 有 planner 写的英文整句就用它并关掉 LM 重写(DeepSeek 的音乐知识 ≫ 本机 0.6B);
    # 否则退回标签串并让 5Hz LM 扩写。
    caption = spec.caption or tag_string
    return {
        "prompt": caption,      # 兼容旧调用方
        "caption": caption,
        "use_cot_caption": not spec.caption_full,
        "keyscale": spec.keyscale or "",
        "timesignature": str(spec.timesignature) if spec.timesignature else "",
        "shift": resolve_shift(spec.preset_id),
        "duration": _LENGTH_MAP.get(length, _LENGTH_MAP["full"]),
        "bpm": spec.bpm,
        "language": spec.language,
        "seed": seed,
    }
```

(d) 在 `generate_song` 中把 `GenerationParams(...)` 调用替换为：

```python
    params = GenerationParams(
        caption=p["caption"],
        lyrics=structured_lyrics,
        duration=float(p["duration"]),
        bpm=p["bpm"],
        keyscale=p["keyscale"],
        timesignature=p["timesignature"],
        vocal_language=p["language"],
        seed=seed if fixed else -1,
        inference_steps=_INFER_STEP,
        shift=p["shift"],
        thinking=True,
        use_cot_caption=p["use_cot_caption"],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_song_gen.py -q`
Expected: 全部 PASS（含此前的 handler 初始化测试）

- [ ] **Step 5: Commit**

```bash
git add src/song_gen.py tests/test_song_gen.py
git commit -m "feat: song_gen 透传 caption/keyscale/timesignature/use_cot_caption,shift 可由环境变量与 preset 决定"
```

---

### Task 9: API — `Overrides.preset`，CJK / 未知 preset → 422

**Files:**
- Modify: `server/models.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `src.presets.get_preset`、`src.textcheck.has_cjk`。
- Produces: `Overrides.preset: str = ""`；请求体 `overrides.genre` / `overrides.mood` 含 CJK 或 `overrides.preset` 未知时 FastAPI 返回 422。

- [ ] **Step 1: Write the failing test**

在 `tests/test_api.py` 末尾追加：

```python


def _with_fake_queue(monkeypatch, tmp_path, name):
    from server import db
    db.init_db(str(tmp_path / name))
    monkeypatch.setattr(appmod.config, "APP_PASSCODE", "")
    captured = {}

    class FakeQ:
        async def enqueue(self, payload, created_by):
            captured.update(payload)
            db.create_job("jP", status="queued", position=1, created_by=created_by)
            return "jP"
    appmod.app.state.queue = FakeQ()
    return captured


def _body(**over):
    base = {"lyrics": "词", "feeling": "说唱", "length": "short", "seed": None,
            "instrumental": False, "overrides": {}}
    base.update(over)
    return base


def test_generate_accepts_known_preset_and_forwards_it(monkeypatch, tmp_path):
    captured = _with_fake_queue(monkeypatch, tmp_path, "p1.db")
    r = client.post("/api/generate", json=_body(overrides={"preset": "hiphop.trap"}))
    assert r.status_code == 200
    assert captured["overrides"]["preset"] == "hiphop.trap"


def test_generate_rejects_unknown_preset_with_422(monkeypatch, tmp_path):
    _with_fake_queue(monkeypatch, tmp_path, "p2.db")
    r = client.post("/api/generate", json=_body(overrides={"preset": "hiphop.nope"}))
    assert r.status_code == 422


def test_generate_rejects_cjk_genre_or_mood_with_422(monkeypatch, tmp_path):
    _with_fake_queue(monkeypatch, tmp_path, "p3.db")
    assert client.post("/api/generate", json=_body(overrides={"genre": ["流行"]})).status_code == 422
    assert client.post("/api/generate", json=_body(overrides={"mood": ["温柔"]})).status_code == 422
    assert client.post("/api/generate", json=_body(overrides={"genre": ["pop"], "mood": ["gentle"]})).status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api.py -q`
Expected: FAIL（`KeyError: 'preset'`；422 断言为 `200 != 422`）

- [ ] **Step 3: Write minimal implementation**

把 `server/models.py` 整体替换为：

```python
from pydantic import BaseModel, Field, field_validator

from src.presets import get_preset
from src.textcheck import has_cjk


class Overrides(BaseModel):
    genre: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    vocal_gender: str = ""
    language: str = ""
    # 风格预设 id;空 → generic。只由 UI 选择,planner 不自动推断。
    preset: str = ""

    @field_validator("genre", "mood")
    @classmethod
    def _english_tags_only(cls, v: list[str]) -> list[str]:
        # 前端显示中文、发送英文;中文混进 caption 会削弱 ACE-Step 的条件控制。
        if any(has_cjk(x) for x in v):
            raise ValueError("genre/mood must be English tags")
        return v

    @field_validator("preset")
    @classmethod
    def _known_preset(cls, v: str) -> str:
        get_preset(v)  # 未知 id 抛 ValueError → FastAPI 422
        return v


class GenerateRequest(BaseModel):
    lyrics: str
    feeling: str = ""
    length: str = "full"      # full | short
    seed: int | None = None
    instrumental: bool = False
    overrides: Overrides = Field(default_factory=Overrides)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_api.py tests/test_queue.py -q`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add server/models.py tests/test_api.py
git commit -m "feat(api): overrides.preset;genre/mood 含中文或 preset 未知时返回 422"
```

---

### Task 10: 灵感示例新增 hip hop（带 preset）

**Files:**
- Modify: `server/inspirations.py`
- Test: `tests/test_api.py`（追加一条）

**Interfaces:**
- Produces: `PRESETS` 每项新增键 `"preset": str`（旧项为 `""`）；新增 hip hop 项 `preset="hiphop.boom_bap"`。

- [ ] **Step 1: Write the failing test**

在 `tests/test_api.py` 末尾追加：

```python


def test_inspirations_include_hiphop_with_preset():
    items = client.get("/api/inspirations").json()["inspirations"]
    assert all("preset" in it for it in items)
    hip = [it for it in items if it["preset"] == "hiphop.boom_bap"]
    assert len(hip) == 1
    assert "[Hook]" in hip[0]["lyrics"] and "hip hop" in hip[0]["feeling"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api.py::test_inspirations_include_hiphop_with_preset -q`
Expected: FAIL（`assert all("preset" in it ...)` 为 False）

- [ ] **Step 3: Write minimal implementation**

把 `server/inspirations.py` 整体替换为：

```python
_HIPHOP_LYRICS = """[Verse]
末班车掠过街角，雨还挂在玻璃上，
City lights, sleepless nights，耳机鼓点替我壮胆。
白天咽下去的话，凌晨铺满半张纸，
Turn the pressure into bars，让沉默也有台词。

他们说路太长，我说刚好边走边唱，
No shortcuts, just footsteps，旧鞋也能踩得响。
出租屋的灯闪两下，我给节拍补个拍，
Small room, big dreams，窗一推，晚风进来。

[Hook]
一拍一拍，把沉默拆开，
My voice, my choice，I'm moving at my own pace.
一步一步，让脚印留下来，
Turn it up, feel the bass，今晚由我主宰。"""

PRESETS = [
    {"title": "毕业的青春回忆", "feeling": "流行，温柔，女声", "preset": "",
     "lyrics": "[Verse]\n那年夏天 微风吹过海边\n[Chorus]\n如果还能再遇见你"},
    {"title": "夜晚城市的孤独", "feeling": "R&B，悲伤，男声", "preset": "",
     "lyrics": "[Verse]\n最后一班地铁 载着疲惫的人"},
    {"title": "恋爱的心动瞬间", "feeling": "流行，浪漫，女声", "preset": "",
     "lyrics": "[Verse]\n你的一个微笑 让整个世界都亮了"},
    {"title": "深夜的中英说唱", "feeling": "hip hop 说唱，男声，夜晚城市，中英混合",
     "preset": "hiphop.boom_bap", "lyrics": _HIPHOP_LYRICS},
    {"title": "海边的治愈旋律", "feeling": "民谣，治愈，纯音乐", "preset": "",
     "lyrics": ""},
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_api.py -q`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add server/inspirations.py tests/test_api.py
git commit -m "feat: 灵感示例新增中英说唱(hiphop.boom_bap preset)"
```

---

### Task 11: 前端 — 类型、AdvancedSettings（中文显示 / 英文发送、preset 控件）

**Files:**
- Modify: `web/lib/types.ts`
- Modify: `web/components/AdvancedSettings.tsx`（整体替换）
- Test: `web/test/AdvancedSettings.test.tsx`（新）

**Interfaces:**
- Produces: `GenerateInput.overrides.preset?: string`；`Inspiration` 接口 `{ title; feeling; lyrics; preset }`；`AdvValue.preset: string`；导出常量 `PRESET_OPTIONS = [{id:"",label:"自动"},{id:"hiphop.boom_bap",label:"Boom Bap"},{id:"hiphop.trap",label:"Trap"}]`；chips 数据 `GENRES: {label,tag}[]`（含 `{label:"Hip hop", tag:"hip hop"}`）、`MOODS: {label,tag}[]`。

- [ ] **Step 1: Write the failing test**

```tsx
// web/test/AdvancedSettings.test.tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import AdvancedSettings, { type AdvValue } from "@/components/AdvancedSettings"

const base: AdvValue = {
  genre: [], mood: [], vocal_gender: "", language: "", length: "full", seed: "", preset: "",
}

describe("AdvancedSettings 发送英文 tag 与 preset", () => {
  it("点中文风格 chip 发送英文 tag", () => {
    const onChange = vi.fn()
    render(<AdvancedSettings value={base} onChange={onChange} />)
    fireEvent.click(screen.getByText("流行"))
    expect(onChange).toHaveBeenCalledWith({ genre: ["pop"] })
  })

  it("点情绪 chip 发送英文 tag", () => {
    const onChange = vi.fn()
    render(<AdvancedSettings value={base} onChange={onChange} />)
    fireEvent.click(screen.getByText("温柔"))
    expect(onChange).toHaveBeenCalledWith({ mood: ["gentle"] })
  })

  it("选 Hip hop 且未选 preset 时默认落到 boom bap", () => {
    const onChange = vi.fn()
    render(<AdvancedSettings value={base} onChange={onChange} />)
    fireEvent.click(screen.getByText("Hip hop"))
    expect(onChange).toHaveBeenCalledWith({ genre: ["hip hop"], preset: "hiphop.boom_bap" })
  })

  it("已选 preset 时选 Hip hop 不改 preset", () => {
    const onChange = vi.fn()
    render(<AdvancedSettings value={{ ...base, preset: "hiphop.trap" }} onChange={onChange} />)
    fireEvent.click(screen.getByText("Hip hop"))
    expect(onChange).toHaveBeenCalledWith({ genre: ["hip hop"] })
  })

  it("preset 分段控件发送 id", () => {
    const onChange = vi.fn()
    render(<AdvancedSettings value={base} onChange={onChange} />)
    fireEvent.click(screen.getByText("Trap"))
    expect(onChange).toHaveBeenCalledWith({ preset: "hiphop.trap" })
  })

  it("chip 选中态按英文 tag 判定", () => {
    render(<AdvancedSettings value={{ ...base, genre: ["pop"] }} onChange={vi.fn()} />)
    expect(screen.getByText("流行").getAttribute("aria-pressed")).toBe("true")
    expect(screen.getByText("摇滚").getAttribute("aria-pressed")).toBe("false")
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run test/AdvancedSettings.test.tsx`
Expected: FAIL（`onChange` 收到 `{ genre: ["流行"] }`；找不到 "Hip hop" / "Trap"）

- [ ] **Step 3: Write minimal implementation**

(a) `web/lib/types.ts`：在 `GenerateInput.overrides` 中追加 `preset?: string`，并在文件末尾追加：

```ts

export interface Inspiration {
  title: string
  feeling: string
  lyrics: string
  /** 风格预设 id;空表示不预选 */
  preset: string
}
```

(b) `web/components/AdvancedSettings.tsx` 整体替换为：

```tsx
"use client"

// 显示中文、发送英文:中文 tag 混进 caption 会削弱 ACE-Step 的条件控制(后端对中文 tag 返回 422)。
export const GENRES = [
  { label: "流行", tag: "pop" },
  { label: "民谣", tag: "folk" },
  { label: "摇滚", tag: "rock" },
  { label: "R&B", tag: "r&b" },
  { label: "电子", tag: "electronic" },
  { label: "古典", tag: "classical" },
  { label: "Hip hop", tag: "hip hop" },
]
export const MOODS = [
  { label: "温柔", tag: "gentle" },
  { label: "悲伤", tag: "sad" },
  { label: "治愈", tag: "healing" },
  { label: "浪漫", tag: "romantic" },
  { label: "欢乐", tag: "joyful" },
]
export const PRESET_OPTIONS = [
  { id: "", label: "自动" },
  { id: "hiphop.boom_bap", label: "Boom Bap" },
  { id: "hiphop.trap", label: "Trap" },
]
const HIPHOP_TAG = "hip hop"
const HIPHOP_DEFAULT_PRESET = "hiphop.boom_bap"

export interface AdvValue {
  genre: string[]
  mood: string[]
  vocal_gender: string
  language: string
  length: string
  seed: string
  preset: string
}

export default function AdvancedSettings({
  value,
  onChange,
}: {
  value: AdvValue
  onChange: (patch: Partial<AdvValue>) => void
}) {
  const chip = (on: boolean) =>
    ({
      padding: "6px 12px",
      borderRadius: 8,
      cursor: "pointer",
      fontSize: 12,
      border: on ? "1px solid var(--brand)" : "1px solid var(--line)",
      background: on ? "rgba(47,107,216,.16)" : "rgba(255,255,255,.55)",
      color: on ? "var(--brand)" : "var(--muted)",
    }) as const
  const toggle = (arr: string[], v: string) =>
    arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]

  function pickGenre(tag: string) {
    const genre = toggle(value.genre, tag)
    // 选 Hip hop 且还没选 preset → 默认 boom bap(用户仍可在下方改成 Trap)
    if (tag === HIPHOP_TAG && genre.includes(tag) && !value.preset) {
      onChange({ genre, preset: HIPHOP_DEFAULT_PRESET })
    } else {
      onChange({ genre })
    }
  }

  return (
    <div>
      <p className="text-muted" style={{ fontSize: 12 }}>
        风格预设
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 12 }}>
        {PRESET_OPTIONS.map((p) => (
          <span
            key={p.id || "auto"}
            role="button"
            aria-pressed={value.preset === p.id}
            style={chip(value.preset === p.id)}
            onClick={() => onChange({ preset: p.id })}
          >
            {p.label}
          </span>
        ))}
      </div>
      <p className="text-muted" style={{ fontSize: 12 }}>
        风格
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 12 }}>
        {GENRES.map((g) => (
          <span
            key={g.tag}
            role="button"
            aria-pressed={value.genre.includes(g.tag)}
            style={chip(value.genre.includes(g.tag))}
            onClick={() => pickGenre(g.tag)}
          >
            {g.label}
          </span>
        ))}
      </div>
      <p className="text-muted" style={{ fontSize: 12 }}>
        情绪
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 12 }}>
        {MOODS.map((m) => (
          <span
            key={m.tag}
            role="button"
            aria-pressed={value.mood.includes(m.tag)}
            style={chip(value.mood.includes(m.tag))}
            onClick={() => onChange({ mood: toggle(value.mood, m.tag) })}
          >
            {m.label}
          </span>
        ))}
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        <select
          value={value.vocal_gender}
          onChange={(e) => onChange({ vocal_gender: e.target.value })}
        >
          <option value="">人声(自动)</option>
          <option value="female">女声</option>
          <option value="male">男声</option>
        </select>
        <select value={value.length} onChange={(e) => onChange({ length: e.target.value })}>
          <option value="full">完整</option>
          <option value="short">短版 Demo</option>
        </select>
        <input
          placeholder="Seed(随机)"
          value={value.seed}
          onChange={(e) => onChange({ seed: e.target.value })}
          style={{ width: 90 }}
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run test/AdvancedSettings.test.tsx && npx tsc --noEmit`
Expected: `6 passed`；tsc 会在 `GenerateForm.tsx` 报 `AdvValue` 缺 `preset` —— Task 12 修（若想此刻绿，可先在 GenerateForm 初始 state 补 `preset: ""`）。

- [ ] **Step 5: Commit**

```bash
git add web/lib/types.ts web/components/AdvancedSettings.tsx web/test/AdvancedSettings.test.tsx
git commit -m "feat(web): 风格 chips 显示中文发送英文;新增风格预设控件,Hip hop 默认 boom bap"
```

---

### Task 12: 前端 — GenerateForm / InspirationList 贯穿 preset

**Files:**
- Modify: `web/components/GenerateForm.tsx`
- Modify: `web/components/InspirationList.tsx`
- Test: `web/test/InspirationList.test.tsx`（新）

**Interfaces:**
- Consumes: `Inspiration` 类型；`AdvValue.preset`。
- Produces: `InspirationList` 的 `onPick(lyrics: string, feeling: string, preset: string)`；`GenerateForm` 提交 `overrides.preset = adv.preset`。

- [ ] **Step 1: Write the failing test**

```tsx
// web/test/InspirationList.test.tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import InspirationList from "@/components/InspirationList"

vi.mock("@/lib/api", () => ({
  getInspirations: vi.fn().mockResolvedValue([
    { title: "深夜的中英说唱", feeling: "hip hop 说唱", lyrics: "[Verse]\nyo", preset: "hiphop.boom_bap" },
  ]),
}))

describe("InspirationList", () => {

  it("点示例时把 lyrics / feeling / preset 一起交给 onPick", async () => {
    const onPick = vi.fn()
    render(<InspirationList onPick={onPick} />)
    fireEvent.click(await screen.findByText("深夜的中英说唱"))
    await waitFor(() =>
      expect(onPick).toHaveBeenCalledWith("[Verse]\nyo", "hip hop 说唱", "hiphop.boom_bap")
    )
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run test/InspirationList.test.tsx`
Expected: FAIL（`onPick` 只收到两个参数）

- [ ] **Step 3: Write minimal implementation**

(a) `web/components/InspirationList.tsx` 整体替换为：

```tsx
"use client"
import { useEffect, useState } from "react"
import { getInspirations } from "@/lib/api"
import type { Inspiration } from "@/lib/types"

export default function InspirationList({
  onPick,
}: {
  onPick: (lyrics: string, feeling: string, preset: string) => void
}) {
  const [items, setItems] = useState<Inspiration[]>([])
  useEffect(() => {
    getInspirations()
      .then(setItems)
      .catch(() => setItems([]))
  }, [])
  return (
    <div className="bg-panel" style={{ padding: 16, borderRadius: 14 }}>
      <h4 style={{ marginTop: 0, fontSize: 14 }}>灵感示例</h4>
      {items.map((it) => (
        <div
          key={it.title}
          onClick={() => onPick(it.lyrics, it.feeling, it.preset || "")}
          style={{
            padding: "9px 0",
            borderBottom: "1px solid var(--line)",
            cursor: "pointer",
          }}
        >
          <div style={{ fontSize: 12.5 }}>{it.title}</div>
          <div className="text-muted" style={{ fontSize: 10.5 }}>
            {it.feeling}
          </div>
        </div>
      ))}
    </div>
  )
}
```

(b) `web/lib/api.ts` 中 `getInspirations` 的返回类型改为使用 `Inspiration`：

```ts
export async function getInspirations() {
  const r = await req<{ inspirations: Inspiration[] }>("/api/inspirations")
  return r.inspirations
}
```
并在文件顶部 import 行改为：`import type { Song, Job, GenerateInput, Inspiration } from "./types"`。

(c) `web/components/GenerateForm.tsx`：
- 初始 state 增加 `preset: ""`：
```tsx
  const [adv, setAdv] = useState<AdvValue>({
    genre: [],
    mood: [],
    vocal_gender: "",
    language: "",
    length: "full",
    seed: "",
    preset: "",
  })
```
- `overrides` 增加 `preset: adv.preset`：
```tsx
      overrides: {
        genre: adv.genre,
        mood: adv.mood,
        vocal_gender: adv.vocal_gender,
        language: adv.language,
        preset: adv.preset,
      },
```
- `InspirationList` 的 `onPick` 改为：
```tsx
        <InspirationList
          onPick={(l, f, preset) => {
            setLyrics(l)
            setFeeling(f)
            setAdv((s) => ({ ...s, preset }))
          }}
        />
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run && npx tsc --noEmit`
Expected: 全部 PASS；tsc 无错误

- [ ] **Step 5: Commit**

```bash
git add web/components/GenerateForm.tsx web/components/InspirationList.tsx web/lib/api.ts web/test/InspirationList.test.tsx
git commit -m "feat(web): 灵感示例与表单贯穿风格预设 id"
```

---

### Task 13: 前端 — SongCard 降级标记显示 reason 文案

**Files:**
- Modify: `web/components/SongCard.tsx`
- Test: `web/test/SongCard.test.tsx`（追加）

**Interfaces:**
- Consumes: `song.llm_status` JSON：`[{stage, ok, reason?}]`。
- Produces: 降级 `title` 形如 `歌曲规划：模型输出含中文；歌词整理：模型改动了歌词，已用规则断行`。

- [ ] **Step 1: Write the failing test**

在 `web/test/SongCard.test.tsx` 的 `describe("SongCard 降级标记")` 内追加：

```tsx
  it("降级说明按阶段列出 reason 文案", () => {
    const degraded = {
      ...song,
      llm_status: JSON.stringify([
        { stage: "歌曲规划", ok: false, reason: "non_english" },
        { stage: "歌词整理", ok: false, reason: "text_changed" },
      ]),
    } as Song
    render(<SongCard song={degraded} onPlay={vi.fn()} />)
    const title = screen.getByText("降级").getAttribute("title") || ""
    expect(title).toContain("歌曲规划：模型输出含中文")
    expect(title).toContain("歌词整理：模型改动了歌词，已用规则断行")
  })

  it("没有 reason 的旧事件仍能显示", () => {
    const degraded = {
      ...song,
      llm_status: JSON.stringify([{ stage: "歌曲规划", ok: false }]),
    } as Song
    render(<SongCard song={degraded} onPlay={vi.fn()} />)
    expect(screen.getByText("降级").getAttribute("title")).toContain("歌曲规划：已回退")
  })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run test/SongCard.test.tsx`
Expected: FAIL（title 为旧文案「歌曲规划、歌词整理已回退…」）

- [ ] **Step 3: Write minimal implementation**

在 `web/components/SongCard.tsx` 中，把 `degradedStages` 函数替换为：

```tsx
const REASON_TEXT: Record<string, string> = {
  llm_error: "模型调用失败",
  bad_json: "模型输出无法解析",
  non_english: "模型输出含中文",
  invalid_spec: "模型输出不合规",
  empty: "模型返回空响应",
  text_changed: "模型改动了歌词，已用规则断行",
}

/** 从 llm_status 里挑出回退的阶段,组成「阶段：原因」说明。字段缺失或格式坏都当作"没有降级"。 */
function degradedNotes(raw: string | null | undefined): string[] {
  if (!raw) return []
  try {
    const events = JSON.parse(raw)
    if (!Array.isArray(events)) return []
    return events
      .filter((e) => e && e.ok === false)
      .map((e) => `${String(e.stage)}：${REASON_TEXT[String(e.reason)] || "已回退"}`)
  } catch {
    return []
  }
}
```

把组件内 `const degraded = degradedStages(song.llm_status)` 改为 `const degraded = degradedNotes(song.llm_status)`，并把徽标的 `title` 改为：

```tsx
              title={`${degraded.join("；")}。这首歌是降级生成的`}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run && npx tsc --noEmit`
Expected: 全部 PASS（原有「有阶段回退时显示降级标记」测试用 `getByTitle(/歌曲规划/)` 仍匹配）

- [ ] **Step 5: Commit**

```bash
git add web/components/SongCard.tsx web/test/SongCard.test.tsx
git commit -m "feat(web): 降级标记显示各阶段回退原因"
```

---

### Task 14: 评测循环文档 + 端到端冒烟 + 收尾

**Files:**
- Create: `docs/superpowers/evals/hiphop-ab.md`
- Verify: 全量测试、类型检查、`ZE_FAKE_GEN=1` 管线冒烟

- [ ] **Step 1: 写评测文档**

```markdown
# hip hop 输入链 A/B 评测记录

## 流程

1. 固定 seed：`1001`、`1002`、`1003`。同一段词（`server/inspirations.py` 的「深夜的中英说唱」）。
2. 每次只改一个变量：caption 骨架 / 断行 / `vocal_language`（`zh` vs `unknown`）/ `ACESTEP_SHIFT`（3.0 vs 1.0）。
3. 提交（把 `<preset>` 换成 `hiphop.boom_bap` 或 `hiphop.trap`）：

   ```bash
   set -a; . ./.env; set +a
   curl -s -X POST http://localhost:8000/api/generate \
     -H "Content-Type: application/json" -H "X-Passcode: $APP_PASSCODE" \
     -d '{"lyrics": "...", "feeling": "hip hop 说唱，男声，夜晚城市，中英混合", "length": "short",
          "seed": 1001, "instrumental": false, "overrides": {"preset": "<preset>"}}'
   ```
4. 从 `backend.log` 抽取 DiT 实际收到的 caption / bpm / keyscale（LM CoT 段 `<|im_start|>assistant` 之后），与我们传入的对照。
5. 两人独立打分（1–5）取均值。

## 记录

| 日期 | seed | preset | 变量 | 我们传入的 caption(摘) | LM 产出 caption(摘) | bpm/key | 吐字 | 音色 | 风格 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-14 | 随机 | (无,基线) | 修复前基线 | `Hip Hop, Rap, 中文说唱, 夜晚…`(DeepSeek 标签串,半中文) | "A smooth, bilingual hip-hop track built on a relaxed lo-fi beat…" | 88 / — | | | | 歌词整理回退(空响应);0.6B LM |
```

- [ ] **Step 2: 全量测试与类型检查**

Run:
```bash
.venv/bin/python -m pytest tests/ -q && (cd web && npx vitest run && npx tsc --noEmit)
```
Expected: 后端全部 PASS（1 skipped 为既有「需真实 API key」）；前端全部 PASS；tsc 无错误。

- [ ] **Step 3: 管线冒烟（不跑模型）**

Run:
```bash
ZE_FAKE_GEN=1 .venv/bin/python - <<'PY'
import sys; sys.path.insert(0, ".")
from src import pipeline
from src.textcheck import has_cjk
r = pipeline.make_song(
    "末班车掠过街角，雨还挂在玻璃上，City lights, sleepless nights，耳机鼓点替我壮胆。",
    "hip hop 说唱，男声，夜晚城市，中英混合",
    length="short", work_dir="/tmp/ze_smoke", overrides={"preset": "hiphop.boom_bap"},
)
s = r["spec"]
print("preset:", r["preset_id"], "| degraded:", r["degraded"], "| events:", r["llm_status"])
print("caption_full:", s.caption_full, "| lang:", s.language, "| bpm:", s.bpm, "| key:", s.keyscale, "| ts:", s.timesignature)
print("caption:", s.caption[:160])
print("--- lyrics ---"); print(r["structured_lyrics"])
assert not has_cjk(s.caption) and s.language in {"zh","en","yue","unknown"}
assert "[Verse - rap]" in r["structured_lyrics"]
print("SMOKE_OK")
PY
```
Expected: 打印 `SMOKE_OK`；若 `.env` 未 source 则 planner/lyrics 会走回退（`degraded: True`，reason `llm_error`），caption 仍为英文骨架 —— 这也是合法结果。若要看 DeepSeek 路径，先 `set -a; . ./.env; set +a`。

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/evals/hiphop-ab.md
git commit -m "docs: hip hop 输入链 A/B 评测记录模板与流程"
```

- [ ] **Step 5: 重启后端并出一首真歌验证**

```bash
launchctl kickstart -k gui/$(id -u)/com.zemusic.backend
```
然后按 `docs/superpowers/evals/hiphop-ab.md` 流程用 `seed=1001`、`preset=hiphop.boom_bap` 出一首短版，把 DiT 实际 caption 与打分填进记录表第二行。**这是本计划的验收：** `llm_status` 两阶段 `ok: true`，DiT caption 含 rap/boom bap 词汇，bpm 在 85–95。
