# 多曲风与人声音色（风格库 + 采样器）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让同一段歌词稳定生成听得出差别的多种曲风与人声音色；用户选了什么，最终 caption 就一定是什么。

**Architecture:** 新增风格采样层，放在 planner 之前：`resolve_genre`（UI 选择 > 感觉关键词 > LLM 识别 > 随机）定曲风，`sample_style` 按 seed 抽出乐器 / 质感 / 年代 / 情绪 / 人声音色 / BPM（遵守互斥、避开最近用过的、支持纯正 / 常规 / 融合三档）。planner 不再自己挑词，只把抽好的要素作为**硬约束**写成英文整句，并按曲风从官方 200 条 caption 中检索示例；caption 经校验（曲风词 / 音色词 / 冲突词 / CJK），不合格重试一次，再失败用抽到的要素渲染骨架。歌词按音色给段落标签加修饰。seed 由流水线补全并落库。前端曲风改为分组网格，新增音色、创意度、风格摘要与「换一种」。

**Tech Stack:** Python 3.11 / pydantic v2 / FastAPI / pytest；Next.js 14 / TypeScript / vitest + @testing-library/react。

**Spec:** `docs/superpowers/specs/2026-10-06-multi-genre-style-design.md`

**预验证（2026-10-06）：** 本计划 Task 1–14 的代码已在临时 worktree 中按原样应用并跑通：后端 `381 passed, 2 skipped`，前端 `105 passed`，`tsc --noEmit` 无错误。实现时若结果不同，先怀疑是否漏抄了某一步。

## Global Constraints

- **只有采样器决定要素**：planner 输出的 `genre` / `mood` / `instrument` / `bpm` / `vocal` 一律被 `StyleDraw` 覆盖；LLM 只负责 caption 措辞、`keyscale`、`timesignature`、`language`、`structure`。
- **确定性**：采样只用 `random.Random(seed)` 局部实例，不碰全局随机状态；同一 seed + 同一输入 → 同一 `StyleDraw`。
- **seed**：`make_song` 收到 `seed=None` 时用 `secrets.randbelow(2**31)` 生成；同一个值同时给采样器与 `song_gen`，并通过结果 `result["seed"]` 落库。
- **caption 校验顺序**：CJK → `non_english`；`preset.caption_keywords` 非空且一个都没命中 → `missing_genre`；音色 `keywords` 一个都没命中 → `missing_timbre`；命中 `preset.avoid` → `conflict`。匹配一律对 caption 做 `lower()` 后子串匹配。
- **重试**：只有 caption 校验失败才重试，且只重试 1 次；`llm_error` / `bad_json` / `invalid_spec` / `non_english`（parse 阶段）直接回退骨架。
- **事件**：沿用 `{"stage", "ok"}`，`ok=False` 时追加 `"reason"`；新增阶段 `曲风识别`，事件额外带 `"source"` ∈ {`ui`,`keyword`,`llm`,`random`}。事件里不得夹带异常原文。
- **曲风识别打分**：命中关键词的**字符长度之和**最高者胜（避免 `pop` 抢走 `city pop` / `pop punk`），平局按 `UI_GENRES` 顺序。
- **段落修饰**：只改**不含 `-`** 的标签行（`[Pre-Chorus]`、`[Verse - whispered]` 不动）；每个标签最多一个修饰；音色的 `section_tags` 优先于 preset 的 `vocal_qualifier`。
- **英文字段**：所有写进 caption 的数据（池、`caption_keywords`、`avoid`、音色 `caption` / `keywords`）不得含 CJK；`keywords`（识别用）与 `label` 可以是中文。
- **数据出处**：`jazz.lounge` 的乐器池与互斥规则改编自 [ddv1982/suno-prompting](https://github.com/ddv1982/suno-prompting)（MIT）；`src/data/caption_bank.json` 来自 ACE-Step-1.5 `examples/text2music`（MIT）。两处都在文件内注明。
- 运行后端测试：`.venv/bin/python -m pytest tests/ -q`；前端：`cd web && npx vitest run`；类型：`cd web && npx tsc --noEmit`。
- 每个任务一个提交；提交信息中文，前缀 `feat:` / `fix:` / `test:` / `docs:` / `refactor:`。
- 不提交：`.DS_Store`、`backend.log`、`findings.md`、`progress.md`、`task_plan.md`、`web/tsconfig.tsbuildinfo`、`.claude/`、`outputs/`。

## 与设计文档的差异（实现时的细化）

| 设计稿 | 本计划 | 理由 |
|---|---|---|
| `bpm: Bpm{min,max,typical}` | 保留 `bpm_range`，新增 `bpm_typical` | 少改调用方与已有测试，语义相同 |
| `VocalTimbre.genders` + 前端不兼容提示 | 本期不做，所有音色不限性别 | 11 种音色没有一个真正只属于单一性别，YAGNI |
| 「换一种」= 同一份歌词 + 用户原始选项 | 同一份歌词 + **同曲风 + 同性别** + 新 seed | 库里没存用户原始 overrides；同曲风换一组要素正是「换一种」的意图 |
| — | 新增 Task 0 先测基线 | §1 成功标准需要「改动前」的 Jaccard 对照 |

## 文件结构

| 文件 | 职责 |
|---|---|
| `src/presets.py` | `Pool` / `Preset` 升级（角色分池、互斥、识别词、校验词、冲突词、情绪池、典型 BPM、音色、融合伙伴）；14 个曲风 + `generic`；`UI_GENRES` |
| `src/vocal_timbres.py`（新） | `VocalTimbre`、`TIMBRES`、`get_timbre` |
| `src/style_sampler.py`（新） | `Locks`、`StyleDraw`、`sample_style`、`parse_recent`、`detect_by_keywords`、`resolve_genre` |
| `src/caption_bank.py`（新） | `tag_caption`、`detect_gender`、`load_bank`、`pick_examples` |
| `src/data/caption_bank.json`（新，生成） | 官方 caption 打标结果 |
| `scripts/build_caption_bank.py`（新） | 生成上面的 JSON |
| `src/spec.py` | `VocalSpec.timbre`、`SongSpec.style_draw` |
| `src/planner.py` | 硬约束提示词、示例检索、`check_caption`、重试、按 draw 渲染骨架 |
| `src/lyric_text.py` / `src/lyrics.py` | `section_tags` 段落修饰 |
| `src/pipeline.py` | 识别 → 采样 → 规划 → 歌词 → 出歌；seed 补全；去掉 genre/mood 事后覆盖 |
| `server/db.py` / `server/queue.py` | `recent_style_draws`；seed 落库 |
| `server/models.py` / `server/routes.py` | `vocal_timbre` / `creativity` 校验；`GET /api/styles` |
| `web/lib/types.ts` / `api.ts` / `styles.ts`（新） | 类型、`getStyles`、`useStyles`、`styleSummary` |
| `web/components/AdvancedSettings.tsx` / `GenerateForm.tsx` | 曲风网格、音色、创意度 |
| `web/components/SongCard.tsx` / `web/app/library/page.tsx` | 风格摘要、新降级原因、「换一种」 |
| `scripts/style_grid.py`（新） | 评测网格 |
| `docs/superpowers/evals/style-grid.md`（新） | 基线与改后结果 |

---

### Task 0: 记录基线（改代码之前）

**Files:**
- Create: `docs/superpowers/evals/style-grid.md`

本任务不改代码，只用**当前**代码量一次 caption 多样性，作为 §8 的对照组。需要 `.env` 里有可用的 LLM key（本机为 DeepSeek）。

- [ ] **Step 1: 跑基线**

```bash
set -a; . ./.env; set +a
.venv/bin/python - <<'EOF'
import itertools, re, statistics
from src import planner
from src.presets import get_preset
import config

FEELINGS = ["流行抒情", "City Pop", "民谣", "摇滚", "流行朋克", "R&B", "电子舞曲",
            "Lo-fi", "爵士", "中国风", "动漫 J-Rock", "Synthwave", "boom bap 说唱", "trap 说唱"]
STOP = {"a", "an", "the", "and", "with", "of", "in", "on", "over", "by", "its", "is", "to", "that", "as", "into", "for"}
toks = lambda c: {t for t in re.findall(r"[a-z][a-z&'-]+", c.lower()) if t not in STOP}
caps = []
for f in FEELINGS:
    s = planner.plan_song(f, preset=get_preset(""), llm_options={"provider": config.LLM_PROVIDER})
    caps.append(s.caption)
    print(f"{f}\t{s.caption[:120]}")
j = [len(toks(a) & toks(b)) / len(toks(a) | toks(b)) for a, b in itertools.combinations(caps, 2)]
print("mean pairwise jaccard:", round(statistics.mean(j), 3))
EOF
```

Expected: 打印 14 行 caption 与一个 Jaccard 均值。

- [ ] **Step 2: 写评测文档**

```markdown
# 风格网格评测（多曲风与人声音色）

## 指标

| 指标 | 计算 |
|---|---|
| 曲风命中率 | caption 命中该曲风 `caption_keywords` 的比例 |
| 两两 Jaccard | caption 小写分词、去停用词后的词集 Jaccard 均值（越低越多样） |
| 降级率 | `llm_status` 中 `ok=False` 的比例 |
| 盲听 | 打乱顺序后评审写出曲风，统计正确率 |

## 基线（改动前，YYYY-MM-DD）

做法：当前代码，preset 为空（generic），「感觉」分别填 14 个曲风名，只跑 planner。

| 感觉 | caption（前 120 字） |
|---|---|
| …… | …… |

两两 Jaccard 均值：**x.xxx**

## 改动后

（Task 15 填写）
```

把 Step 1 的输出填进表格与均值。

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/evals/style-grid.md
git commit -m "docs(evals): 风格网格评测基线(改动前)"
```

---

### Task 1: Preset 结构升级（角色分池 / 互斥 / 新字段），迁移现有 3 个 preset

**Files:**
- Modify: `src/presets.py`
- Test: `tests/test_presets.py`

**Interfaces:**
- Produces: `POOL_ORDER = ("harmonic","color","rhythm","rare")`；`Pool(items, pick_min=1, pick_max=1, chance=1.0)`；`Preset` 新字段 `keywords` / `caption_keywords` / `avoid` / `instrument_pools` / `exclusions` / `mood_pool` / `bpm_typical` / `vocal_timbres` / `fusion_partners`；只读属性 `Preset.instrument_pool`（按 `POOL_ORDER` 展平）；`Preset.bpm_default()` 优先 `bpm_typical`；`Preset.render_skeleton(vocal_gender=None, *, instruments=None, textures=None, era=None, vocal=None)`。

- [ ] **Step 1: Write the failing test**

在 `tests/test_presets.py` 顶部 import 改为：

```python
import pytest
from src.presets import POOL_ORDER, PRESETS, Pool, Preset, get_preset
from src.textcheck import has_cjk
```

文件末尾追加：

```python
def _mini(**over):
    base = dict(id="x", label="x", family="x", caption_skeleton="{instruments}",
                structure=["Verse"])
    base.update(over)
    return Preset(**base)


def test_instrument_pool_flattens_role_pools_in_order():
    p = _mini(instrument_pools={"rhythm": Pool(items=["drums"]),
                                "harmonic": Pool(items=["piano", "rhodes"])})
    assert POOL_ORDER == ("harmonic", "color", "rhythm", "rare")
    assert p.instrument_pool == ["piano", "rhodes", "drums"]


def test_unknown_pool_role_rejected():
    with pytest.raises(ValueError):
        _mini(instrument_pools={"lead": Pool(items=["a"])})


def test_pool_pick_range_validated():
    with pytest.raises(ValueError):
        Pool(items=["a"], pick_min=2, pick_max=1)
    with pytest.raises(ValueError):
        Pool(items=["a"], pick_max=2)            # 比池子还大
    with pytest.raises(ValueError):
        Pool(items=["a"], chance=0)


def test_exclusions_must_reference_pool_items():
    with pytest.raises(ValueError):
        _mini(instrument_pools={"harmonic": Pool(items=["a"])}, exclusions=[("a", "zzz")])


def test_bpm_typical_must_be_in_range_and_wins_default():
    with pytest.raises(ValueError):
        _mini(bpm_range=(80, 90), bpm_typical=120)
    assert _mini(bpm_range=(80, 100), bpm_typical=84).bpm_default() == 84
    assert _mini(bpm_range=(80, 100)).bpm_default() == 90      # 未设 typical → 中点


def test_render_skeleton_accepts_drawn_elements():
    s = PRESETS["hiphop.trap"].render_skeleton(
        instruments=["808 sub-bass", "bell melody"], textures=["dark"], era="2020s",
        vocal="male rapid-fire rap flow")
    assert "808 sub-bass, bell melody" in s and "dark" in s and "2020s" in s
    assert "male rapid-fire rap flow" in s


def test_migrated_hiphop_presets_keep_behavior():
    assert PRESETS["hiphop.trap"].bpm_default() == 140
    assert PRESETS["hiphop.boom_bap"].bpm_default() == 90
    assert "808 sub-bass" in PRESETS["hiphop.trap"].instrument_pool
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_presets.py -q`
Expected: FAIL with `ImportError: cannot import name 'POOL_ORDER'`

- [ ] **Step 3: Write minimal implementation**

`src/presets.py` 的 import 改为 `from pydantic import BaseModel, Field, model_validator`，在 `AceStepKnobs` 之后、`Preset` 之前加入：

```python
# 编曲角色,采样时按此顺序逐池抽取。
# 角色分池 + 互斥规则的做法参考 ddv1982/suno-prompting(MIT)。
POOL_ORDER = ("harmonic", "color", "rhythm", "rare")


class Pool(BaseModel):
    """一个编曲角色的乐器池:每次抽 pick_min..pick_max 件;chance<1 表示整池按概率参与(rare 用)。"""
    items: list[str]
    pick_min: int = 1
    pick_max: int = 1
    chance: float = 1.0

    @model_validator(mode="after")
    def _check(self):
        if not 0 <= self.pick_min <= self.pick_max <= len(self.items):
            raise ValueError("need 0 <= pick_min <= pick_max <= len(items)")
        if not 0 < self.chance <= 1:
            raise ValueError("chance must be in (0, 1]")
        return self
```

把 `Preset` 整个类替换为：

```python
class Preset(BaseModel):
    id: str
    label: str
    family: str
    # 英文整句模板,占位符 {instruments} {texture} {era} {vocal}
    caption_skeleton: str
    genre_tags: list[str] = Field(default_factory=list)
    # 曲风识别用(中英皆可,小写子串匹配)
    keywords: list[str] = Field(default_factory=list)
    # caption 校验:至少命中一个(英文,小写);空 = 不校验曲风词
    caption_keywords: list[str] = Field(default_factory=list)
    # 冲突词:caption 命中即不合格
    avoid: list[str] = Field(default_factory=list)
    instrument_pools: dict[str, Pool] = Field(default_factory=dict)
    exclusions: list[tuple[str, str]] = Field(default_factory=list)
    texture_pool: list[str] = Field(default_factory=list)
    era_pool: list[str] = Field(default_factory=list)
    mood_pool: list[str] = Field(default_factory=list)
    bpm_range: tuple[int, int] = (60, 160)
    bpm_typical: int | None = None
    keyscale_hint: str = ""
    timesignature: int = 4
    structure: list[str]
    vocal_qualifier: str = ""
    vocal_gender_default: str = "female"
    # 本曲风适合的人声音色 id(见 src/vocal_timbres.py),未锁定时从中采样
    vocal_timbres: list[str] = Field(default_factory=list)
    # 融合档可选的伙伴曲风 id(人工挑选的兼容对)
    fusion_partners: list[str] = Field(default_factory=list)
    lyric_rules: LyricRules = Field(default_factory=LyricRules)
    acestep: AceStepKnobs = Field(default_factory=AceStepKnobs)
    # 兜底示例:示例库检索不到时才注入 planner
    examples: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self):
        unknown = set(self.instrument_pools) - set(POOL_ORDER)
        if unknown:
            raise ValueError(f"unknown pool roles: {sorted(unknown)}")
        items = set(self.instrument_pool)
        for a, b in self.exclusions:
            if a not in items or b not in items:
                raise ValueError(f"exclusion ({a}, {b}) references an item not in pools")
        lo, hi = self.bpm_range
        if self.bpm_typical is not None and not lo <= self.bpm_typical <= hi:
            raise ValueError("bpm_typical out of bpm_range")
        return self

    @property
    def instrument_pool(self) -> list[str]:
        """所有角色池按 POOL_ORDER 展平(planner 提示词与旧调用方用)。"""
        out: list[str] = []
        for role in POOL_ORDER:
            pool = self.instrument_pools.get(role)
            if pool:
                out.extend(pool.items)
        return out

    def render_skeleton(self, vocal_gender: str | None = None, *,
                        instruments: list[str] | None = None,
                        textures: list[str] | None = None,
                        era: str | None = None,
                        vocal: str | None = None) -> str:
        """planner 降级时用的英文 caption。传了采样结果就用采样结果,否则每个必选池取第一项。"""
        if instruments is None:
            instruments = [p.items[0] for r in POOL_ORDER
                           if (p := self.instrument_pools.get(r)) and p.pick_min > 0][:3]
        if textures is None:
            textures = self.texture_pool[:2]
        era = era or (self.era_pool[0] if self.era_pool else "modern")
        vocal = vocal or f"{vocal_gender or self.vocal_gender_default} {self.vocal_qualifier or 'vocal'}"
        return self.caption_skeleton.format(
            instruments=", ".join(instruments) or "drums, bass, keys",
            texture=", ".join(textures) or "clean, balanced",
            era=era, vocal=vocal,
        )

    def bpm_default(self) -> int:
        if self.bpm_typical is not None:
            return self.bpm_typical
        lo, hi = self.bpm_range
        return (lo + hi) // 2
```

把 `_GENERIC` / `_BOOM_BAP` / `_TRAP` 替换为：

```python
_GENERIC = Preset(
    id="generic", label="自动", family="generic",
    caption_skeleton=(
        "A {era} track featuring {instruments}, with a {texture} production "
        "and a {vocal} carrying the melody."
    ),
    genre_tags=["pop"],
    mood_pool=["warm", "hopeful", "nostalgic"],
    bpm_range=(60, 160),
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"],
    vocal_timbres=["clear", "breathy", "deep", "powerful"],
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
    keywords=["boom bap", "老派", "old school", "说唱", "嘻哈", "hip hop", "hiphop", "rap"],
    caption_keywords=["boom bap"],
    avoid=["supersaw", "festival", "banjo"],
    instrument_pools={
        "harmonic": Pool(items=["jazzy piano sample", "Rhodes sample", "soul guitar loop"]),
        "color": Pool(items=["muted trumpet stabs", "vinyl crackle", "soul vocal sample"],
                      pick_max=2),
        "rhythm": Pool(items=["dusty drum break", "upright bass"], pick_min=2, pick_max=2),
        "rare": Pool(items=["turntable scratches"], pick_min=0, pick_max=1, chance=0.3),
    },
    texture_pool=["warm", "gritty", "lo-fi", "dusty"],
    era_pool=["90s", "golden era"],
    mood_pool=["confident", "nocturnal", "introspective", "nostalgic", "gritty"],
    bpm_range=(85, 95), bpm_typical=90,
    keyscale_hint="minor",
    structure=["Intro", "Verse", "Hook", "Verse", "Hook", "Outro"],
    vocal_qualifier="rap",
    vocal_gender_default="male",
    vocal_timbres=["rap_laidback", "rap_rapid", "deep", "raspy"],
    fusion_partners=["jazz.lounge", "lofi.chill"],
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
    keywords=["trap", "808", "drill", "陷阱"],
    caption_keywords=["trap"],
    avoid=["banjo", "acoustic ballad", "jazz trio"],
    instrument_pools={
        "harmonic": Pool(items=["dark synth pads", "eerie piano melody", "bell melody"]),
        "color": Pool(items=["vocal chops", "plucked synth", "choir pad"], pick_min=0),
        "rhythm": Pool(items=["808 sub-bass", "rolling hi-hats", "hard-hitting trap drums"],
                       pick_min=2, pick_max=3),
        "rare": Pool(items=["flute loop"], pick_min=0, pick_max=1, chance=0.25),
    },
    texture_pool=["punchy", "dark", "modern", "hard-hitting"],
    era_pool=["modern", "2020s"],
    mood_pool=["dark", "aggressive", "confident", "menacing", "hypnotic"],
    bpm_range=(130, 150), bpm_typical=140,
    keyscale_hint="minor",
    structure=["Intro", "Verse", "Hook", "Verse", "Hook", "Outro"],
    vocal_qualifier="rap",
    vocal_gender_default="male",
    vocal_timbres=["rap_rapid", "rap_laidback", "raspy", "deep"],
    fusion_partners=["electronic.dance", "rnb.soul"],
    examples=[
        "A Chinese trap song with aggressive male rap, heavy 808s, and dark atmospheric "
        "synths. The production features hard-hitting drums, rolling hi-hats, vocal "
        "chops, and an intense energy throughout.",
    ],
)
```

`fusion_partners` / `vocal_timbres` 里引用的 id 在 Task 2、3 才落地，由 Task 3 的注册表完整性测试统一校验。

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 全部通过（`test_render_skeleton_fills_placeholders` 仍命中 `dusty drum break` 与 `male rap`；planner 仍通过 `instrument_pool` 属性取词）。

- [ ] **Step 5: Commit**

```bash
git add src/presets.py tests/test_presets.py
git commit -m "refactor: Preset 改为按编曲角色分池,新增互斥/识别词/校验词/音色/融合字段"
```

---

### Task 2: 人声音色表 `src/vocal_timbres.py`

**Files:**
- Create: `src/vocal_timbres.py`
- Test: `tests/test_vocal_timbres.py`

**Interfaces:**
- Produces: `VocalTimbre(id, label, caption, keywords, section_tags)`；`TIMBRES: dict[str, VocalTimbre]`（11 项，插入顺序即前端展示顺序）；`get_timbre(id) -> VocalTimbre | None`（空串 → `None`，未知 → `ValueError`）。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vocal_timbres.py
import pytest
from src.textcheck import has_cjk
from src.vocal_timbres import TIMBRES, get_timbre

EXPECTED = ["clear", "breathy", "raspy", "deep", "powerful", "falsetto",
            "soft_whisper", "theatrical", "rap_rapid", "rap_laidback", "choir"]


def test_registry_order_and_ids():
    assert list(TIMBRES) == EXPECTED


@pytest.mark.parametrize("tid", EXPECTED)
def test_caption_is_english_and_hits_own_keywords(tid):
    t = TIMBRES[tid]
    assert has_cjk(t.label)
    assert not has_cjk(t.caption) and not any(has_cjk(k) for k in t.keywords)
    assert any(k in t.caption.lower() for k in t.keywords), t.caption


@pytest.mark.parametrize("tid", EXPECTED)
def test_section_tags_only_for_verse_or_chorus(tid):
    assert set(TIMBRES[tid].section_tags) <= {"Verse", "Chorus"}
    assert not any(has_cjk(v) for v in TIMBRES[tid].section_tags.values())


def test_get_timbre():
    assert get_timbre("") is None
    assert get_timbre("breathy").label == "气声"
    with pytest.raises(ValueError):
        get_timbre("robot")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vocal_timbres.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.vocal_timbres'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/vocal_timbres.py
"""人声音色表:前端显示中文,写进 caption 的是英文短语。

keywords 用于校验 caption 是否真的写了这个音色;section_tags 给歌词段落标签加修饰,
如 {"Chorus": "powerful"} → [Chorus - powerful](只改不带修饰的标签,见 lyric_text)。
"""
from pydantic import BaseModel, Field


class VocalTimbre(BaseModel):
    id: str
    label: str
    caption: str
    keywords: list[str]
    section_tags: dict[str, str] = Field(default_factory=dict)


_ALL = [
    VocalTimbre(id="clear", label="清亮", caption="bright, clear vocal",
                keywords=["clear", "bright"]),
    VocalTimbre(id="breathy", label="气声", caption="breathy, airy vocal",
                keywords=["breathy", "airy"], section_tags={"Verse": "breathy"}),
    # 不用 gritty 当关键词:它常被当作质感词出现,会让音色校验误判通过
    VocalTimbre(id="raspy", label="烟嗓", caption="raspy, husky vocal",
                keywords=["raspy", "husky"]),
    VocalTimbre(id="deep", label="低沉磁性", caption="deep, warm low-register vocal",
                keywords=["deep", "low-register", "baritone"]),
    VocalTimbre(id="powerful", label="高亢有力", caption="powerful, belting vocal",
                keywords=["powerful", "belting"], section_tags={"Chorus": "powerful"}),
    VocalTimbre(id="falsetto", label="假声", caption="delicate falsetto vocal",
                keywords=["falsetto"], section_tags={"Chorus": "falsetto"}),
    VocalTimbre(id="soft_whisper", label="温柔耳语", caption="soft, hushed, whispered vocal",
                keywords=["whisper", "hushed"], section_tags={"Verse": "whispered"}),
    VocalTimbre(id="theatrical", label="戏剧化", caption="theatrical, dramatic vocal",
                keywords=["theatrical", "dramatic", "soaring"],
                section_tags={"Chorus": "soaring"}),
    VocalTimbre(id="rap_rapid", label="快嘴说唱", caption="rapid-fire rap flow",
                keywords=["rapid-fire", "rapid", "fast rap"], section_tags={"Verse": "rap"}),
    VocalTimbre(id="rap_laidback", label="慵懒说唱", caption="laid-back, relaxed rap flow",
                keywords=["laid-back", "relaxed"], section_tags={"Verse": "rap"}),
    VocalTimbre(id="choir", label="合唱", caption="layered choir harmonies",
                keywords=["choir"], section_tags={"Chorus": "choir"}),
]

TIMBRES: dict[str, VocalTimbre] = {t.id: t for t in _ALL}


def get_timbre(timbre_id: str | None) -> VocalTimbre | None:
    """空 → None(不指定);未知 id 抛 ValueError(API 层转 422)。"""
    if not timbre_id:
        return None
    try:
        return TIMBRES[timbre_id]
    except KeyError as exc:
        raise ValueError(f"未知人声音色: {timbre_id}") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_vocal_timbres.py -q`
Expected: `24 passed`

- [ ] **Step 5: Commit**

```bash
git add src/vocal_timbres.py tests/test_vocal_timbres.py
git commit -m "feat: 人声音色表(11 种,含段落修饰)"
```

---
### Task 3: 新增 12 个曲风 + `UI_GENRES` + 注册表完整性测试

**Files:**
- Modify: `src/presets.py`
- Test: `tests/test_presets.py`

**Interfaces:**
- Consumes: Task 1 的 `Pool` / `Preset`；Task 2 的 `TIMBRES`（只在测试里）。
- Produces: `UI_GENRES: list[str]`（14 个，前端展示与随机挑选的顺序）；`PRESETS` = `generic` + 14 个曲风。

- [ ] **Step 1: Write the failing test**

在 `tests/test_presets.py`：

1. import 增加 `UI_GENRES` 与 `from src.vocal_timbres import TIMBRES`；
2. 把 `test_registry_has_generic_and_two_hiphop_presets` 替换为下面第一个测试；
3. 把 `test_preset_english_fields_have_no_cjk` 替换为下面第二个测试；
4. 追加其余测试。

```python
EXPECTED_GENRES = [
    "pop.ballad", "pop.city_pop", "folk.acoustic", "rock.band", "rock.pop_punk",
    "rnb.soul", "electronic.dance", "lofi.chill", "jazz.lounge", "cn.guofeng",
    "rock.anime", "electronic.synthwave", "hiphop.boom_bap", "hiphop.trap",
]


def test_registry_is_generic_plus_ui_genres():
    assert UI_GENRES == EXPECTED_GENRES
    assert set(PRESETS) == {"generic", *EXPECTED_GENRES}


@pytest.mark.parametrize("pid", list(PRESETS))
def test_preset_english_fields_have_no_cjk(pid):
    p = PRESETS[pid]
    for text in [p.caption_skeleton, *p.genre_tags, *p.instrument_pool, *p.texture_pool,
                 *p.era_pool, *p.mood_pool, *p.caption_keywords, *p.avoid, *p.examples,
                 p.keyscale_hint, p.vocal_qualifier, p.render_skeleton()]:
        assert not has_cjk(text), text


@pytest.mark.parametrize("pid", EXPECTED_GENRES)
def test_ui_genre_data_complete(pid):
    p = PRESETS[pid]
    assert has_cjk(p.label) or p.label.isascii()
    assert p.keywords and p.caption_keywords and p.examples
    assert p.caption_keywords == [k.lower() for k in p.caption_keywords]
    assert {"harmonic", "color", "rhythm"} <= set(p.instrument_pools)   # 纯正档要 harmonic+rhythm,融合要 color
    assert p.texture_pool and p.era_pool and p.mood_pool
    assert p.vocal_timbres and set(p.vocal_timbres) <= set(TIMBRES)
    assert p.fusion_partners and set(p.fusion_partners) <= set(EXPECTED_GENRES)
    assert pid not in p.fusion_partners
    assert p.bpm_typical is not None


@pytest.mark.parametrize("pid", EXPECTED_GENRES)
def test_own_words_and_partner_colors_never_hit_avoid(pid):
    p = PRESETS[pid]
    words = [*p.instrument_pool, *p.texture_pool, *p.era_pool, *p.mood_pool,
             *(TIMBRES[t].caption for t in p.vocal_timbres)]
    for partner in p.fusion_partners:
        words += PRESETS[partner].instrument_pools["color"].items
    for w in words:
        assert not any(a.lower() in w.lower() for a in p.avoid), (pid, w)


@pytest.mark.parametrize("pid", EXPECTED_GENRES)
def test_default_skeleton_contains_genre_word_and_no_avoid(pid):
    s = PRESETS[pid].render_skeleton().lower()
    assert any(k in s for k in PRESETS[pid].caption_keywords), s
    assert not any(a.lower() in s for a in PRESETS[pid].avoid), s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_presets.py -q`
Expected: FAIL with `ImportError: cannot import name 'UI_GENRES'`

- [ ] **Step 3: Write minimal implementation**

在 `src/presets.py` 的 `_TRAP` 之后、`PRESETS = …` 之前加入 12 个曲风，并把注册表改为：

```python
_BALLAD = Preset(
    id="pop.ballad", label="流行抒情", family="pop",
    caption_skeleton=(
        "A {era} pop ballad featuring {instruments}, with a {texture} production and a "
        "{vocal} carrying an emotional melody that swells into the chorus."
    ),
    genre_tags=["pop", "ballad"],
    keywords=["抒情", "情歌", "慢歌", "流行", "ballad", "pop"],
    caption_keywords=["ballad"],
    avoid=["808", "trap", "distorted guitar", "dubstep"],
    instrument_pools={
        "harmonic": Pool(items=["grand piano", "felt piano", "electric piano"]),
        "color": Pool(items=["string section", "cello", "acoustic guitar", "airy synth pads",
                             "soft choir"], pick_max=2),
        "rhythm": Pool(items=["soft drums", "brushed drums", "electric bass"]),
        "rare": Pool(items=["music box", "glockenspiel"], pick_min=0, pick_max=1, chance=0.2),
    },
    texture_pool=["warm", "lush", "polished", "intimate"],
    era_pool=["modern", "2010s", "2000s"],
    mood_pool=["tender", "bittersweet", "nostalgic", "hopeful", "melancholic"],
    bpm_range=(60, 84), bpm_typical=72,
    structure=["Intro", "Verse", "Pre-Chorus", "Chorus", "Verse", "Chorus", "Bridge",
               "Chorus", "Outro"],
    vocal_timbres=["clear", "breathy", "powerful", "falsetto", "soft_whisper"],
    fusion_partners=["rnb.soul", "folk.acoustic"],
    examples=[
        "An emotional pop ballad that opens with gentle felt piano and a breathy female "
        "vocal, then swells with a string section and soft drums into a soaring, "
        "heartfelt chorus.",
    ],
)

_CITY_POP = Preset(
    id="pop.city_pop", label="City Pop", family="pop",
    caption_skeleton=(
        "A {era} city pop track with {instruments}. The production is {texture}, and a "
        "{vocal} glides over a groovy, nostalgic beat."
    ),
    genre_tags=["city pop", "pop"],
    keywords=["city pop", "citypop", "城市流行", "都市", "日系", "复古流行"],
    caption_keywords=["city pop"],
    avoid=["808", "trap", "metal", "distorted"],
    instrument_pools={
        "harmonic": Pool(items=["Rhodes electric piano", "bright synth keys",
                                "clean electric guitar chords"]),
        "color": Pool(items=["funky slap bass", "brass section", "saxophone solo",
                             "lush strings"], pick_max=2),
        "rhythm": Pool(items=["groovy live drums", "four-on-the-floor drums"]),
        "rare": Pool(items=["vibraphone", "synth arpeggio"], pick_min=0, pick_max=1,
                     chance=0.3),
    },
    texture_pool=["glossy", "bright", "polished", "retro"],
    era_pool=["80s", "late 80s Japanese", "80s Tokyo"],
    mood_pool=["nostalgic", "breezy", "romantic", "dreamy", "carefree"],
    bpm_range=(96, 120), bpm_typical=108,
    structure=["Intro", "Verse", "Pre-Chorus", "Chorus", "Verse", "Chorus", "Outro"],
    vocal_timbres=["clear", "breathy", "soft_whisper", "falsetto"],
    fusion_partners=["jazz.lounge", "electronic.synthwave"],
    examples=[
        "A breezy 80s city pop song with a glossy Rhodes electric piano, funky slap bass "
        "and a brass section over groovy live drums, sung by a clear, airy female vocal "
        "with a nostalgic, romantic mood.",
    ],
)

_FOLK = Preset(
    id="folk.acoustic", label="民谣", family="folk",
    caption_skeleton=(
        "A {era} acoustic folk song built on {instruments}, with a {texture} recording "
        "and a {vocal} telling the story."
    ),
    genre_tags=["folk", "acoustic"],
    keywords=["民谣", "木吉他", "吉他弹唱", "folk", "acoustic"],
    caption_keywords=["folk"],
    avoid=["808", "synth bass", "edm", "trap", "distorted"],
    instrument_pools={
        "harmonic": Pool(items=["fingerpicked acoustic guitar", "strummed acoustic guitar",
                                "nylon-string guitar"]),
        "color": Pool(items=["harmonica", "cello", "violin", "mandolin", "soft piano",
                             "banjo"], pick_max=2),
        "rhythm": Pool(items=["light percussion", "upright bass", "cajon"], pick_min=0),
        "rare": Pool(items=["accordion", "glockenspiel"], pick_min=0, pick_max=1, chance=0.2),
    },
    exclusions=[("mandolin", "banjo")],
    texture_pool=["warm", "organic", "intimate", "raw"],
    era_pool=["modern", "70s", "2010s indie"],
    mood_pool=["nostalgic", "tender", "wistful", "peaceful", "heartfelt"],
    bpm_range=(70, 110), bpm_typical=90,
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"],
    vocal_gender_default="male",
    vocal_timbres=["clear", "breathy", "raspy", "deep", "soft_whisper"],
    fusion_partners=["pop.ballad", "cn.guofeng"],
    examples=[
        "A warm acoustic folk song with fingerpicked guitar, harmonica and a touch of "
        "cello, recorded with an intimate, organic feel and a gentle male vocal that "
        "tells a nostalgic story.",
    ],
)

_ROCK = Preset(
    id="rock.band", label="摇滚", family="rock",
    caption_skeleton=(
        "A {era} rock track driven by {instruments}. The mix is {texture}, and a "
        "{vocal} pushes through anthemic choruses."
    ),
    genre_tags=["rock"],
    keywords=["摇滚", "乐队", "硬摇", "rock", "band"],
    caption_keywords=["rock"],
    avoid=["808", "trap", "lo-fi"],
    instrument_pools={
        "harmonic": Pool(items=["distorted electric guitar", "crunchy rhythm guitar",
                                "overdriven guitar riffs"]),
        "color": Pool(items=["lead guitar solo", "Hammond organ", "piano stabs",
                             "string pads"]),
        "rhythm": Pool(items=["punchy live drums", "driving bass guitar"], pick_min=2,
                       pick_max=2),
        "rare": Pool(items=["tambourine", "cowbell"], pick_min=0, pick_max=1, chance=0.25),
    },
    texture_pool=["raw", "punchy", "gritty", "arena-sized"],
    era_pool=["90s", "2000s", "modern", "70s classic"],
    mood_pool=["defiant", "energetic", "triumphant", "rebellious", "anthemic"],
    bpm_range=(100, 140), bpm_typical=120,
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"],
    vocal_gender_default="male",
    vocal_timbres=["raspy", "powerful", "clear", "theatrical"],
    fusion_partners=["rock.pop_punk", "rock.anime"],
    examples=[
        "An energetic rock anthem driven by crunchy distorted guitars, punchy live drums "
        "and a driving bass line, with a raspy, powerful male vocal and a lead guitar "
        "solo before the final chorus.",
    ],
)

_POP_PUNK = Preset(
    id="rock.pop_punk", label="流行朋克", family="rock",
    caption_skeleton=(
        "A {era} pop punk anthem with {instruments}. It sounds {texture}, with a "
        "{vocal} shouting a catchy, sing-along chorus."
    ),
    genre_tags=["pop punk", "punk"],
    keywords=["流行朋克", "朋克", "pop punk", "punk"],
    caption_keywords=["punk"],
    avoid=["808", "ballad", "jazz", "orchestral"],
    instrument_pools={
        "harmonic": Pool(items=["fast power chords", "palm-muted guitars",
                                "bright distorted guitars"]),
        "color": Pool(items=["lead guitar hooks", "synth leads", "gang vocal shouts"],
                      pick_min=0),
        "rhythm": Pool(items=["fast punk drums", "driving bass guitar"], pick_min=2,
                       pick_max=2),
        "rare": Pool(items=["handclaps"], pick_min=0, pick_max=1, chance=0.3),
    },
    texture_pool=["energetic", "raw", "bright", "youthful"],
    era_pool=["2000s", "modern", "early 2000s"],
    mood_pool=["rebellious", "carefree", "youthful", "energetic", "bittersweet"],
    bpm_range=(150, 185), bpm_typical=165,
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"],
    vocal_gender_default="male",
    vocal_timbres=["raspy", "powerful", "clear"],
    fusion_partners=["rock.band", "electronic.dance"],
    examples=[
        "A fast, youthful pop punk song with bright distorted power chords, energetic "
        "punk drums and a catchy shouted chorus from a raspy male vocal, full of "
        "carefree, rebellious energy.",
    ],
)

_RNB = Preset(
    id="rnb.soul", label="R&B / Soul", family="rnb",
    caption_skeleton=(
        "A {era} R&B soul track with {instruments}. The production is {texture}, and a "
        "{vocal} delivers smooth, soulful runs."
    ),
    genre_tags=["r&b", "soul"],
    keywords=["节奏布鲁斯", "灵魂乐", "律动", "r&b", "rnb", "soul"],
    caption_keywords=["r&b", "soul", "rnb"],
    avoid=["distorted", "metal", "punk", "banjo"],
    instrument_pools={
        "harmonic": Pool(items=["Rhodes electric piano", "warm keys",
                                "neo-soul guitar chords"]),
        "color": Pool(items=["lush strings", "muted horns", "layered backing vocals",
                             "synth bass"], pick_max=2),
        "rhythm": Pool(items=["laid-back drums", "smooth bass line", "finger snaps"],
                       pick_max=2),
        "rare": Pool(items=["vibraphone", "harp"], pick_min=0, pick_max=1, chance=0.2),
    },
    exclusions=[("synth bass", "smooth bass line")],
    texture_pool=["smooth", "silky", "warm", "intimate"],
    era_pool=["90s", "modern", "2000s", "70s"],
    mood_pool=["sensual", "late-night", "soulful", "romantic", "yearning"],
    bpm_range=(70, 100), bpm_typical=85,
    structure=["Intro", "Verse", "Pre-Chorus", "Chorus", "Verse", "Chorus", "Bridge",
               "Chorus", "Outro"],
    vocal_timbres=["breathy", "falsetto", "deep", "powerful", "soft_whisper"],
    fusion_partners=["pop.ballad", "hiphop.boom_bap"],
    examples=[
        "A smooth late-night R&B song with warm Rhodes chords, laid-back drums and a "
        "deep bass line, featuring a silky female vocal with soulful runs and layered "
        "backing harmonies.",
    ],
)

_DANCE = Preset(
    id="electronic.dance", label="电子舞曲", family="electronic",
    caption_skeleton=(
        "A {era} electronic dance track built on {instruments}. The mix is {texture}, "
        "with a {vocal} over a euphoric build and drop."
    ),
    genre_tags=["edm", "dance", "electronic"],
    keywords=["电子舞曲", "舞曲", "蹦迪", "edm", "dance", "house", "club"],
    caption_keywords=["dance", "edm", "house"],
    avoid=["acoustic ballad", "banjo", "jazz trio", "upright bass"],
    instrument_pools={
        "harmonic": Pool(items=["supersaw synth chords", "plucky synth lead",
                                "bright synth stabs"]),
        "color": Pool(items=["vocal chops", "risers and sweeps", "arpeggiated synths",
                             "piano house chords"], pick_max=2),
        "rhythm": Pool(items=["four-on-the-floor kick", "sidechained bass", "crisp claps"],
                       pick_min=2, pick_max=2),
        "rare": Pool(items=["acid synth line", "talk box"], pick_min=0, pick_max=1,
                     chance=0.25),
    },
    texture_pool=["euphoric", "punchy", "polished", "festival-sized"],
    era_pool=["modern", "2010s", "2020s"],
    mood_pool=["euphoric", "energetic", "uplifting", "hypnotic", "dreamy"],
    bpm_range=(118, 130), bpm_typical=124,
    structure=["Intro", "Verse", "Pre-Chorus", "Chorus", "Verse", "Chorus", "Outro"],
    vocal_timbres=["clear", "powerful", "breathy", "falsetto"],
    fusion_partners=["electronic.synthwave", "pop.city_pop"],
    examples=[
        "An uplifting electronic dance track with a four-on-the-floor kick, sidechained "
        "bass and bright supersaw chords, building through risers into a euphoric drop "
        "with a clear, powerful female vocal.",
    ],
)

_LOFI = Preset(
    id="lofi.chill", label="Lo-fi", family="chill",
    caption_skeleton=(
        "A {era} lo-fi chill track with {instruments}. The sound is {texture}, and a "
        "{vocal} hums over a relaxed, dusty groove."
    ),
    genre_tags=["lo-fi", "chill"],
    keywords=["低保真", "学习", "放松", "咖啡", "lofi", "lo-fi", "chill"],
    caption_keywords=["lo-fi", "lofi"],
    avoid=["distorted", "metal", "festival", "supersaw"],
    instrument_pools={
        "harmonic": Pool(items=["mellow electric piano", "jazzy guitar chords", "soft piano"]),
        "color": Pool(items=["vinyl crackle", "tape hiss", "warm synth pads", "muted trumpet"],
                      pick_max=2),
        "rhythm": Pool(items=["dusty boom bap drums", "soft kick and snare", "round bass"],
                       pick_max=2),
        "rare": Pool(items=["rain ambience", "wind chimes"], pick_min=0, pick_max=1,
                     chance=0.3),
    },
    exclusions=[("dusty boom bap drums", "soft kick and snare")],
    texture_pool=["warm", "hazy", "lo-fi", "mellow"],
    era_pool=["modern", "90s-inspired", "bedroom"],
    mood_pool=["relaxed", "nostalgic", "cozy", "dreamy", "melancholic"],
    bpm_range=(70, 90), bpm_typical=80,
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"],
    vocal_timbres=["soft_whisper", "breathy", "deep", "rap_laidback"],
    fusion_partners=["jazz.lounge", "hiphop.boom_bap"],
    examples=[
        "A cozy lo-fi chill track with mellow electric piano, vinyl crackle and dusty "
        "drums, with a soft, hushed female vocal drifting over a warm, hazy groove.",
    ],
)

# 乐器池与互斥规则改编自 ddv1982/suno-prompting 的 jazz 定义(MIT License)
_JAZZ = Preset(
    id="jazz.lounge", label="爵士", family="chill",
    caption_skeleton=(
        "A {era} jazz song with {instruments}. The recording feels {texture}, and a "
        "{vocal} sings with a swinging, late-night elegance."
    ),
    genre_tags=["jazz"],
    keywords=["爵士", "摇摆", "酒吧", "jazz", "swing", "bossa"],
    caption_keywords=["jazz", "swing", "bossa nova"],
    avoid=["808", "edm", "distorted", "trap"],
    instrument_pools={
        "harmonic": Pool(items=["Rhodes", "grand piano", "hollowbody guitar",
                                "Hammond organ"]),
        "color": Pool(items=["tenor sax", "alto sax", "muted trumpet", "flugelhorn",
                             "trombone", "vibraphone", "clarinet"], pick_max=2),
        "rhythm": Pool(items=["upright bass", "walking bass", "brushed drums", "ride cymbal"],
                       pick_max=2),
        "rare": Pool(items=["congas", "bongos"], pick_min=0, pick_max=1, chance=0.2),
    },
    exclusions=[("tenor sax", "alto sax"), ("muted trumpet", "flugelhorn"),
                ("upright bass", "walking bass"), ("congas", "bongos")],
    texture_pool=["smooth", "warm", "intimate", "live"],
    era_pool=["50s", "60s", "modern"],
    mood_pool=["smooth", "sophisticated", "late-night", "laid-back", "romantic"],
    bpm_range=(80, 160), bpm_typical=110,
    structure=["Intro", "Verse", "Chorus", "Instrumental", "Verse", "Chorus", "Outro"],
    vocal_timbres=["deep", "breathy", "soft_whisper", "clear"],
    fusion_partners=["rnb.soul", "lofi.chill"],
    examples=[
        "A smooth late-night jazz song with brushed drums, walking upright bass and a "
        "grand piano, a muted trumpet answering a warm, breathy female vocal in an "
        "intimate live-room recording.",
    ],
)

_GUOFENG = Preset(
    id="cn.guofeng", label="中国风", family="cn",
    caption_skeleton=(
        "A {era} Chinese-style pop song blending {instruments}. The production is "
        "{texture}, and a {vocal} sings a graceful, pentatonic melody."
    ),
    genre_tags=["chinese traditional", "c-pop"],
    keywords=["中国风", "古风", "国风", "戏腔", "古筝", "chinese style", "guofeng"],
    caption_keywords=["chinese-style", "chinese style", "guzheng", "erhu", "pipa",
                      "pentatonic"],
    avoid=["banjo", "country", "metal"],
    instrument_pools={
        "harmonic": Pool(items=["guzheng", "pipa", "soft piano"]),
        "color": Pool(items=["erhu", "dizi bamboo flute", "xiao flute", "guqin",
                             "string section"], pick_max=2),
        "rhythm": Pool(items=["soft drums", "traditional percussion", "deep bass"]),
        "rare": Pool(items=["temple bells", "chinese gong"], pick_min=0, pick_max=1,
                     chance=0.25),
    },
    exclusions=[("dizi bamboo flute", "xiao flute")],
    texture_pool=["elegant", "cinematic", "ethereal", "lush"],
    era_pool=["modern", "ancient-inspired"],
    mood_pool=["poetic", "melancholic", "graceful", "nostalgic", "epic"],
    bpm_range=(66, 96), bpm_typical=80,
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Bridge", "Chorus", "Outro"],
    vocal_timbres=["clear", "breathy", "theatrical", "falsetto"],
    fusion_partners=["pop.ballad", "electronic.dance"],
    examples=[
        "An elegant Chinese-style pop song that opens with guzheng and dizi bamboo flute, "
        "adds an erhu line and soft drums, and features a clear, graceful female vocal "
        "singing a poetic pentatonic melody.",
    ],
)

_ANIME = Preset(
    id="rock.anime", label="动漫 / J-Rock", family="rock",
    caption_skeleton=(
        "A {era} anime-style J-rock song with {instruments}. The mix is {texture}, and a "
        "{vocal} soars through a dramatic, high-energy chorus."
    ),
    genre_tags=["j-rock", "anime"],
    keywords=["动漫", "动画", "番剧", "日系摇滚", "热血", "anime", "j-rock"],
    caption_keywords=["anime", "j-rock"],
    avoid=["808", "lo-fi", "country", "jazz trio"],
    instrument_pools={
        "harmonic": Pool(items=["fast distorted guitars", "bright overdriven guitar riffs"]),
        "color": Pool(items=["synth brass fanfare", "piano runs", "string section",
                             "lead guitar solo"], pick_max=2),
        "rhythm": Pool(items=["driving rock drums", "busy bass guitar"], pick_min=2,
                       pick_max=2),
        "rare": Pool(items=["synth arpeggios", "glockenspiel"], pick_min=0, pick_max=1,
                     chance=0.3),
    },
    texture_pool=["bright", "dense", "punchy", "dramatic"],
    era_pool=["2010s", "modern", "2000s"],
    mood_pool=["triumphant", "adventurous", "passionate", "exhilarating", "bittersweet"],
    bpm_range=(135, 185), bpm_typical=150,
    structure=["Intro", "Verse", "Pre-Chorus", "Chorus", "Verse", "Chorus", "Bridge",
               "Chorus", "Outro"],
    vocal_gender_default="male",
    vocal_timbres=["powerful", "clear", "theatrical", "raspy"],
    fusion_partners=["rock.band", "electronic.dance"],
    examples=[
        "An explosive anime-style J-rock song with fast distorted guitars, a synth brass "
        "fanfare and driving drums, led by a powerful, theatrical male vocal that soars "
        "into a triumphant chorus.",
    ],
)

_SYNTHWAVE = Preset(
    id="electronic.synthwave", label="Synthwave", family="electronic",
    caption_skeleton=(
        "A {era} synthwave track with {instruments}. The sound is {texture}, and a "
        "{vocal} floats over neon-lit, retro-futuristic grooves."
    ),
    genre_tags=["synthwave", "retro"],
    keywords=["合成器", "复古电子", "赛博", "霓虹", "80年代", "synthwave", "retrowave"],
    caption_keywords=["synthwave", "retrowave"],
    avoid=["banjo", "upright bass", "trap", "acoustic ballad"],
    instrument_pools={
        "harmonic": Pool(items=["analog synth pads", "warm polysynth chords"]),
        "color": Pool(items=["bright synth lead", "electric guitar solo", "saxophone",
                             "arpeggiated synth bass"], pick_max=2),
        "rhythm": Pool(items=["gated reverb drums", "linn drum machine", "pulsing bass"],
                       pick_max=2),
        "rare": Pool(items=["vocoder", "talk box"], pick_min=0, pick_max=1, chance=0.25),
    },
    exclusions=[("gated reverb drums", "linn drum machine"),
                ("arpeggiated synth bass", "pulsing bass")],
    texture_pool=["neon", "shimmering", "nostalgic", "glossy"],
    era_pool=["80s", "retro 80s", "modern retro"],
    mood_pool=["nostalgic", "nocturnal", "dreamy", "driving", "melancholic"],
    bpm_range=(84, 118), bpm_typical=100,
    structure=["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"],
    vocal_gender_default="male",
    vocal_timbres=["clear", "breathy", "deep", "falsetto"],
    fusion_partners=["pop.city_pop", "rock.band"],
    examples=[
        "A nocturnal 80s synthwave track with shimmering analog synth pads, gated reverb "
        "drums and a pulsing bass, a bright synth lead and a deep male vocal drifting "
        "through a neon-lit, nostalgic atmosphere.",
    ],
)

# 前端展示顺序,也是随机挑曲风的候选集(generic 不在其中,只作最终兜底)
UI_GENRES: list[str] = [
    "pop.ballad", "pop.city_pop", "folk.acoustic", "rock.band", "rock.pop_punk",
    "rnb.soul", "electronic.dance", "lofi.chill", "jazz.lounge", "cn.guofeng",
    "rock.anime", "electronic.synthwave", "hiphop.boom_bap", "hiphop.trap",
]

PRESETS: dict[str, Preset] = {p.id: p for p in (
    _GENERIC, _BALLAD, _CITY_POP, _FOLK, _ROCK, _POP_PUNK, _RNB, _DANCE, _LOFI, _JAZZ,
    _GUOFENG, _ANIME, _SYNTHWAVE, _BOOM_BAP, _TRAP,
)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 全部通过。若 `test_own_words_and_partner_colors_never_hit_avoid` 或 `test_default_skeleton_contains_genre_word_and_no_avoid` 失败，按报出的 `(pid, word)` 改数据（删冲突词或换措辞），不要放宽测试。

- [ ] **Step 5: Commit**

```bash
git add src/presets.py tests/test_presets.py
git commit -m "feat: 风格库扩到 14 个曲风(含融合伙伴与音色),UI_GENRES"
```

---

### Task 4: 采样器 `sample_style`

**Files:**
- Create: `src/style_sampler.py`
- Test: `tests/test_style_sampler.py`

**Interfaces:**
- Consumes: `POOL_ORDER`、`Preset`、`get_preset`。
- Produces:
  - `CREATIVITY_LEVELS = ("pure", "normal", "fusion")`、`MAX_INSTRUMENTS = 5`、`RECENT_WEIGHT = 0.3`、`DEFAULT_TIMBRE = "clear"`；
  - `Locks(moods: list[str] = [], vocal_gender: str = "", vocal_timbre: str = "")`；
  - `StyleDraw(preset_id, instruments, textures, era, moods, vocal_timbre, vocal_gender, bpm, fusion_id=None, seed)`；
  - `sample_style(preset, *, seed: int, locks: Locks | None = None, creativity: str = "normal", recent: Sequence[StyleDraw] = ()) -> StyleDraw`（未知 creativity 抛 `ValueError`）；
  - `parse_recent(items: list) -> list[StyleDraw]`（跳过非法项）。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_style_sampler.py
import pytest
from src.presets import UI_GENRES, get_preset
from src.style_sampler import Locks, StyleDraw, parse_recent, sample_style


@pytest.mark.parametrize("pid", UI_GENRES)
def test_same_seed_same_draw(pid):
    p = get_preset(pid)
    assert sample_style(p, seed=7) == sample_style(p, seed=7)


@pytest.mark.parametrize("pid", UI_GENRES)
def test_different_seeds_vary(pid):
    p = get_preset(pid)
    draws = {sample_style(p, seed=s).model_dump_json(exclude={"seed"}) for s in range(20)}
    assert len(draws) > 1


@pytest.mark.parametrize("pid", UI_GENRES)
def test_invariants_hold_for_every_level(pid):
    p = get_preset(pid)
    lo, hi = p.bpm_range
    for s in range(40):
        for level in ("pure", "normal", "fusion"):
            d = sample_style(p, seed=s, creativity=level)
            assert d.preset_id == pid and d.seed == s
            assert 1 <= len(d.instruments) <= 5
            assert len(set(d.instruments)) == len(d.instruments)
            for a, b in p.exclusions:
                assert not (a in d.instruments and b in d.instruments), (a, b)
            assert lo <= d.bpm <= hi
            assert d.vocal_timbre in p.vocal_timbres
            assert d.vocal_gender == p.vocal_gender_default
            assert d.era in p.era_pool and set(d.textures) <= set(p.texture_pool)


def test_locks_are_kept_verbatim():
    d = sample_style(get_preset("folk.acoustic"), seed=1,
                     locks=Locks(moods=["sad"], vocal_gender="female", vocal_timbre="choir"))
    assert d.moods == ["sad"] and d.vocal_gender == "female" and d.vocal_timbre == "choir"


def test_pure_uses_typical_bpm_and_only_harmonic_rhythm():
    p = get_preset("jazz.lounge")
    allowed = set(p.instrument_pools["harmonic"].items) | set(p.instrument_pools["rhythm"].items)
    for s in range(30):
        d = sample_style(p, seed=s, creativity="pure")
        assert d.bpm == p.bpm_default() and d.fusion_id is None
        assert set(d.instruments) <= allowed
        assert d.era == p.era_pool[0] and len(d.textures) == 1


def test_fusion_adds_partner_and_one_partner_color():
    p = get_preset("pop.city_pop")
    for s in range(30):
        d = sample_style(p, seed=s, creativity="fusion")
        assert d.fusion_id in p.fusion_partners
        partner_color = set(get_preset(d.fusion_id).instrument_pools["color"].items)
        assert set(d.instruments) & partner_color


def test_unknown_creativity_raises():
    with pytest.raises(ValueError):
        sample_style(get_preset("rock.band"), seed=1, creativity="wild")


def _draw(**over):
    base = dict(preset_id="hiphop.boom_bap", instruments=["jazzy piano sample"],
                textures=["warm"], era="90s", moods=["confident"], vocal_timbre="deep",
                vocal_gender="male", bpm=90, seed=0)
    base.update(over)
    return StyleDraw(**base)


def test_recent_instruments_are_down_weighted():
    p = get_preset("hiphop.boom_bap")
    target = "jazzy piano sample"
    recent = [_draw(instruments=[target])]
    base = sum(target in sample_style(p, seed=s).instruments for s in range(300))
    down = sum(target in sample_style(p, seed=s, recent=recent).instruments
               for s in range(300))
    assert down < base * 0.7


def test_recent_timbres_are_down_weighted():
    p = get_preset("hiphop.boom_bap")
    recent = [_draw(vocal_timbre="rap_laidback")]
    base = sum(sample_style(p, seed=s).vocal_timbre == "rap_laidback" for s in range(300))
    down = sum(sample_style(p, seed=s, recent=recent).vocal_timbre == "rap_laidback"
               for s in range(300))
    assert down < base * 0.7


def test_parse_recent_skips_invalid_items():
    good = _draw().model_dump()
    assert parse_recent([{"bad": 1}, good, None, "x"]) == [_draw()]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_style_sampler.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.style_sampler'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/style_sampler.py
"""风格采样:在 planner 之前按 seed 抽出本次的曲风要素。

LLM 自己挑词会收敛到最常见的搭配(同一 preset 的 caption 几乎逐字相同);
这里用 seed 驱动的局部随机数抽取,保证可复现、遵守互斥、避开最近用过的。
"""
import random
from collections.abc import Sequence

from pydantic import BaseModel, Field, ValidationError

from src.presets import POOL_ORDER, Preset, get_preset

CREATIVITY_LEVELS = ("pure", "normal", "fusion")
MAX_INSTRUMENTS = 5
RECENT_WEIGHT = 0.3     # 最近用过的乐器/音色降权到这个比例
DEFAULT_TIMBRE = "clear"


class Locks(BaseModel):
    """用户在界面上锁定的维度:锁定即原样使用,不参与采样。"""
    moods: list[str] = Field(default_factory=list)
    vocal_gender: str = ""
    vocal_timbre: str = ""


class StyleDraw(BaseModel):
    preset_id: str
    instruments: list[str]
    textures: list[str]
    era: str
    moods: list[str]
    vocal_timbre: str
    vocal_gender: str
    bpm: int
    fusion_id: str | None = None
    seed: int


def parse_recent(items: list) -> list[StyleDraw]:
    """从库里读出的 style_draw 字典 → StyleDraw;老数据或坏数据直接跳过。"""
    out: list[StyleDraw] = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        try:
            out.append(StyleDraw.model_validate(it))
        except ValidationError:
            continue
    return out


def _conflicts(item: str, chosen: list[str], exclusions) -> bool:
    return any((item == a and b in chosen) or (item == b and a in chosen)
               for a, b in exclusions)


def _pick(rng: random.Random, items: list[str], avoid: set[str]) -> str:
    weights = [RECENT_WEIGHT if i in avoid else 1.0 for i in items]
    return rng.choices(items, weights=weights, k=1)[0]


def _sample(rng: random.Random, pool: list[str], k: int) -> list[str]:
    return rng.sample(pool, min(k, len(pool)))


def _draw_instruments(rng, preset: Preset, creativity: str, avoid: set[str],
                      cap: int) -> list[str]:
    chosen: list[str] = []
    roles = ("harmonic", "rhythm") if creativity == "pure" else POOL_ORDER
    for role in roles:
        pool = preset.instrument_pools.get(role)
        if not pool:
            continue
        if creativity != "pure" and pool.chance < 1 and rng.random() >= pool.chance:
            continue
        k = max(pool.pick_min, 1) if creativity == "pure" else rng.randint(pool.pick_min,
                                                                           pool.pick_max)
        for _ in range(k):
            if len(chosen) >= cap:
                return chosen
            cands = [i for i in pool.items
                     if i not in chosen and not _conflicts(i, chosen, preset.exclusions)]
            if not cands:
                break
            chosen.append(_pick(rng, cands, avoid))
    return chosen


def sample_style(preset: Preset, *, seed: int, locks: Locks | None = None,
                 creativity: str = "normal",
                 recent: Sequence[StyleDraw] = ()) -> StyleDraw:
    if creativity not in CREATIVITY_LEVELS:
        raise ValueError(f"未知创意度: {creativity}")
    locks = locks or Locks()
    rng = random.Random(seed)
    pure = creativity == "pure"
    used_instruments = {i for d in recent for i in d.instruments}
    used_timbres = {d.vocal_timbre for d in recent}

    # 融合档给伙伴曲风留一个位置
    cap = MAX_INSTRUMENTS - (1 if creativity == "fusion" else 0)
    instruments = _draw_instruments(rng, preset, creativity, used_instruments, cap)

    fusion_id = None
    if creativity == "fusion" and preset.fusion_partners:
        fusion_id = rng.choice(preset.fusion_partners)
        color = get_preset(fusion_id).instrument_pools.get("color")
        # 伙伴的乐器也要过本曲风的互斥表(如 lofi 的 muted trumpet 与 jazz 的 flugelhorn)
        cands = [i for i in (color.items if color else [])
                 if i not in instruments and not _conflicts(i, instruments, preset.exclusions)]
        if cands:
            instruments.append(_pick(rng, cands, used_instruments))

    textures = _sample(rng, preset.texture_pool, 1 if pure else rng.randint(1, 2))
    if preset.era_pool:
        era = preset.era_pool[0] if pure else rng.choice(preset.era_pool)
    else:
        era = "modern"
    moods = (list(locks.moods) if locks.moods
             else _sample(rng, preset.mood_pool, 1 if pure else rng.randint(1, 2)))
    if locks.vocal_timbre:
        timbre = locks.vocal_timbre
    elif preset.vocal_timbres:
        timbre = _pick(rng, preset.vocal_timbres, used_timbres)
    else:
        timbre = DEFAULT_TIMBRE

    typical = preset.bpm_default()
    lo, hi = preset.bpm_range
    bpm = typical if pure else rng.randint(max(lo, typical - 8), min(hi, typical + 8))

    return StyleDraw(
        preset_id=preset.id, instruments=instruments, textures=textures, era=era,
        moods=moods, vocal_timbre=timbre,
        vocal_gender=locks.vocal_gender or preset.vocal_gender_default,
        bpm=bpm, fusion_id=fusion_id, seed=seed,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_style_sampler.py -q`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add src/style_sampler.py tests/test_style_sampler.py
git commit -m "feat: 风格采样器(seed 确定性/互斥/防重复/纯正-常规-融合)"
```

---

### Task 5: 曲风识别 `resolve_genre`

**Files:**
- Modify: `src/style_sampler.py`
- Test: `tests/test_style_sampler.py`

**Interfaces:**
- Consumes: `UI_GENRES`、`PRESETS`、`src.llm.complete`。
- Produces:
  - `detect_by_keywords(text: str) -> str | None`；
  - `resolve_genre(preset_id: str | None, feeling: str, *, seed: int, recent_ids: Sequence[str] = (), llm_options: dict | None = None, status_events: list[dict] | None = None) -> Preset`；
  - 事件 `{"stage": "曲风识别", "ok": bool, "source": "ui"|"keyword"|"llm"|"random"}`，失败时加 `"reason"` ∈ {`llm_error`, `unknown_genre`}。
  - `recent_ids` 为**新 → 旧**顺序，随机时避开前 3 个。

- [ ] **Step 1: Write the failing test**

在 `tests/test_style_sampler.py` 末尾追加：

```python
from src import style_sampler
from src.style_sampler import detect_by_keywords, resolve_genre


@pytest.mark.parametrize("text,expected", [
    ("想要 City Pop 的感觉", "pop.city_pop"),       # 不能被 "pop" 抢走
    ("pop punk 青春", "rock.pop_punk"),
    ("民谣吉他，女声", "folk.acoustic"),
    ("女声 R&B 深夜", "rnb.soul"),
    ("夏天的海边", None),
    ("", None),
])
def test_detect_by_keywords(text, expected):
    assert detect_by_keywords(text) == expected


def test_resolve_ui_choice_wins_and_skips_llm(monkeypatch):
    monkeypatch.setattr(style_sampler.llm, "complete",
                        lambda *a, **k: pytest.fail("不该调用 LLM"))
    events = []
    p = resolve_genre("jazz.lounge", "摇滚", seed=1, status_events=events)
    assert p.id == "jazz.lounge"
    assert events == [{"stage": "曲风识别", "ok": True, "source": "ui"}]


def test_resolve_unknown_ui_id_raises():
    with pytest.raises(ValueError):
        resolve_genre("nope", "", seed=1)


def test_resolve_keyword_before_llm(monkeypatch):
    monkeypatch.setattr(style_sampler.llm, "complete",
                        lambda *a, **k: pytest.fail("不该调用 LLM"))
    events = []
    assert resolve_genre("", "来点 synthwave", seed=1, status_events=events).id == \
        "electronic.synthwave"
    assert events[0]["source"] == "keyword"


def test_resolve_llm_when_keywords_miss(monkeypatch):
    seen = {}

    def fake(prompt, **k):
        seen.update(prompt=prompt, **k)
        return "我觉得是 jazz.lounge"
    monkeypatch.setattr(style_sampler.llm, "complete", fake)
    events = []
    p = resolve_genre("", "夜里的小酒馆", seed=1, llm_options={"provider": "deepseek"},
                      status_events=events)
    assert p.id == "jazz.lounge" and seen["provider"] == "deepseek"
    assert "rock.anime" in seen["prompt"] and "夜里的小酒馆" in seen["prompt"]
    assert events == [{"stage": "曲风识别", "ok": True, "source": "llm"}]


def test_resolve_llm_garbage_falls_back_to_random(monkeypatch):
    monkeypatch.setattr(style_sampler.llm, "complete", lambda *a, **k: "不知道")
    events = []
    p = resolve_genre("", "夜里的小酒馆", seed=1, status_events=events)
    assert p.id in UI_GENRES
    assert events == [{"stage": "曲风识别", "ok": False, "source": "random",
                       "reason": "unknown_genre"}]


def test_resolve_llm_error_does_not_leak(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("bad key sk-SECRET")
    monkeypatch.setattr(style_sampler.llm, "complete", boom)
    events = []
    resolve_genre("", "夜里的小酒馆", seed=1, status_events=events)
    assert events[0]["reason"] == "llm_error"
    assert "SECRET" not in str(events)


def test_resolve_empty_feeling_is_random_without_llm(monkeypatch):
    monkeypatch.setattr(style_sampler.llm, "complete",
                        lambda *a, **k: pytest.fail("不该调用 LLM"))
    events = []
    a = resolve_genre("", "  ", seed=5, status_events=events)
    assert a.id == resolve_genre("", "", seed=5).id          # 同 seed 同结果
    assert events == [{"stage": "曲风识别", "ok": True, "source": "random"}]


def test_resolve_random_avoids_three_most_recent():
    recent = ["pop.ballad", "rock.band", "lofi.chill", "jazz.lounge"]
    picked = {resolve_genre("", "", seed=s, recent_ids=recent).id for s in range(200)}
    assert not picked & {"pop.ballad", "rock.band", "lofi.chill"}
    assert "jazz.lounge" in picked                           # 第 4 个不避
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_style_sampler.py -q`
Expected: FAIL with `ImportError: cannot import name 'detect_by_keywords'`

- [ ] **Step 3: Write minimal implementation**

`src/style_sampler.py` 顶部 import 增加：

```python
import logging

from src import llm
from src.presets import POOL_ORDER, PRESETS, UI_GENRES, Preset, get_preset
```

（替换原来的 `from src.presets import POOL_ORDER, Preset, get_preset`。）文件末尾追加：

```python
_DETECT_SYSTEM = "你是曲风分类器。只输出一个曲风 id,不要任何解释。"
_RECENT_AVOID = 3


def detect_by_keywords(text: str) -> str | None:
    """按命中关键词的字符长度之和打分:"city pop" 同时命中 pop 时,长词胜出。"""
    t = (text or "").lower()
    best, best_score = None, 0
    for pid in UI_GENRES:
        score = sum(len(k) for k in PRESETS[pid].keywords if k.lower() in t)
        if score > best_score:
            best, best_score = pid, score
    return best


def _detect_by_llm(text: str, llm_options: dict | None) -> str | None:
    menu = "\n".join(f"{pid}: {PRESETS[pid].label}" for pid in UI_GENRES)
    prompt = f"歌曲感觉描述:{text}\n可选曲风(id: 名称):\n{menu}\n只输出最合适的一个 id。"
    out = llm.complete(prompt, system=_DETECT_SYSTEM, **(llm_options or {})) or ""
    for pid in UI_GENRES:
        if pid in out:
            return pid
    return None


def _emit(events: list[dict] | None, ok: bool, source: str, reason: str | None = None):
    if events is None:
        return
    ev: dict = {"stage": "曲风识别", "ok": ok, "source": source}
    if not ok:
        ev["reason"] = reason
    events.append(ev)


def resolve_genre(preset_id: str | None, feeling: str, *, seed: int,
                  recent_ids: Sequence[str] = (), llm_options: dict | None = None,
                  status_events: list[dict] | None = None) -> Preset:
    """UI 选择 > 感觉关键词 > LLM 识别 > 随机(避开最近 3 首)。未知 UI id 抛 ValueError。"""
    if preset_id:
        preset = get_preset(preset_id)
        _emit(status_events, True, "ui")
        return preset

    pid = detect_by_keywords(feeling)
    if pid:
        _emit(status_events, True, "keyword")
        return PRESETS[pid]

    reason = None
    if (feeling or "").strip():
        try:
            pid = _detect_by_llm(feeling, llm_options)
        except Exception as e:  # noqa: BLE001 — 事件里不带异常原文(可能含 key)
            logging.warning("genre detection LLM failed, picking random: %s", type(e).__name__)
            reason = "llm_error"
        else:
            if pid:
                _emit(status_events, True, "llm")
                return PRESETS[pid]
            reason = "unknown_genre"

    avoid = set(list(recent_ids)[:_RECENT_AVOID])
    pool = [p for p in UI_GENRES if p not in avoid] or list(UI_GENRES)
    pid = random.Random(seed).choice(pool)
    _emit(status_events, reason is None, "random", reason)
    return PRESETS[pid]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_style_sampler.py -q`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add src/style_sampler.py tests/test_style_sampler.py
git commit -m "feat: 曲风识别(UI > 关键词 > LLM > 随机避开最近 3 首)"
```

---
### Task 6: 官方 caption 示例库

**Files:**
- Create: `src/caption_bank.py`
- Create: `scripts/build_caption_bank.py`
- Create（生成）: `src/data/caption_bank.json`
- Test: `tests/test_caption_bank.py`

**Interfaces:**
- Produces: `BANK_PATH`；`tag_caption(caption) -> list[str]`；`detect_gender(caption) -> "male"|"female"|"mixed"|"none"`；`load_bank(path=BANK_PATH) -> list[dict]`（每项 `{id, caption, genres, gender}`）；`pick_examples(preset_id, gender, rng, k=2, bank=None) -> list[str]`（先同曲风同性别，再同曲风，最后回退 `preset.examples`；同一 rng 状态结果确定）。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_caption_bank.py
import random
from src.caption_bank import detect_gender, load_bank, pick_examples, tag_caption
from src.presets import UI_GENRES, get_preset
from src.textcheck import has_cjk


def test_tag_caption_uses_caption_keywords():
    assert "pop.city_pop" in tag_caption("A dreamy 80s City Pop song with slap bass")
    assert "jazz.lounge" in tag_caption("A swing jazz tune")
    assert tag_caption("A song about nothing") == []


def test_detect_gender():
    assert detect_gender("a breathy female vocal") == "female"
    assert detect_gender("a raspy male vocal") == "male"           # 不能被 female 误伤
    assert detect_gender("a male and female duet") == "mixed"
    assert detect_gender("an instrumental piece") == "none"


BANK = [
    {"id": "a", "caption": "city pop female A", "genres": ["pop.city_pop"], "gender": "female"},
    {"id": "b", "caption": "city pop female B", "genres": ["pop.city_pop"], "gender": "female"},
    {"id": "c", "caption": "city pop male C", "genres": ["pop.city_pop"], "gender": "male"},
]


def test_pick_examples_prefers_same_gender_then_widens():
    got = pick_examples("pop.city_pop", "male", random.Random(1), k=2, bank=BANK)
    assert got[0] == "city pop male C" and len(got) == 2


def test_pick_examples_is_deterministic():
    a = pick_examples("pop.city_pop", "female", random.Random(3), k=2, bank=BANK)
    b = pick_examples("pop.city_pop", "female", random.Random(3), k=2, bank=BANK)
    assert a == b


def test_pick_examples_falls_back_to_preset_examples():
    got = pick_examples("cn.guofeng", "female", random.Random(1), k=2, bank=BANK)
    assert got == get_preset("cn.guofeng").examples


def test_real_bank_loads_and_is_english():
    bank = load_bank()
    assert len(bank) >= 150
    assert all(not has_cjk(e["caption"]) for e in bank)
    covered = {g for e in bank for g in e["genres"]}
    assert len(covered & set(UI_GENRES)) >= 8      # 其余曲风回退 preset.examples
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_caption_bank.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.caption_bank'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/caption_bank.py
"""官方 caption 示例库:按曲风检索 2–3 条,给 planner 当句式与维度参考。

数据由 scripts/build_caption_bank.py 从 ACE-Step-1.5 的 examples/text2music(MIT)
生成并入库,运行时不依赖 ACE-Step 目录。
"""
import json
import os
import random
import re
from functools import lru_cache

from src.presets import PRESETS, UI_GENRES, get_preset

BANK_PATH = os.path.join(os.path.dirname(__file__), "data", "caption_bank.json")

_FEMALE = re.compile(r"\b(female|woman|women|girl)\b")
_MALE = re.compile(r"\b(male|man|men|boy)\b")


def tag_caption(caption: str) -> list[str]:
    c = caption.lower()
    return [pid for pid in UI_GENRES
            if any(k in c for k in PRESETS[pid].caption_keywords)]


def detect_gender(caption: str) -> str:
    c = caption.lower()
    f, m = bool(_FEMALE.search(c)), bool(_MALE.search(c))
    if f and m:
        return "mixed"
    return "female" if f else "male" if m else "none"


@lru_cache(maxsize=4)
def load_bank(path: str = BANK_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["entries"]


def pick_examples(preset_id: str, gender: str, rng: random.Random, k: int = 2,
                  bank: list[dict] | None = None) -> list[str]:
    bank = load_bank() if bank is None else bank
    same = [e for e in bank if preset_id in e["genres"]]
    exact = [e for e in same if e["gender"] == gender]
    chosen = rng.sample(exact, min(k, len(exact)))
    rest = [e for e in same if e not in chosen]
    if len(chosen) < k and rest:
        chosen += rng.sample(rest, min(k - len(chosen), len(rest)))
    return [e["caption"] for e in chosen] or list(get_preset(preset_id).examples)
```

```python
# scripts/build_caption_bank.py
"""一次性:把 ACE-Step 官方 examples/text2music 的 caption 打标后写入 src/data/caption_bank.json。

用法(项目根目录): .venv/bin/python scripts/build_caption_bank.py [examples_dir]
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config  # noqa: E402
from src.caption_bank import BANK_PATH, detect_gender, tag_caption  # noqa: E402
from src.presets import UI_GENRES  # noqa: E402
from src.textcheck import has_cjk  # noqa: E402


def main(src_dir: str) -> None:
    entries = []
    for path in sorted(glob.glob(os.path.join(src_dir, "*.json"))):
        with open(path, encoding="utf-8") as f:
            cap = (json.load(f).get("caption") or "").strip()
        if not cap or has_cjk(cap):
            continue
        entries.append({"id": os.path.splitext(os.path.basename(path))[0], "caption": cap,
                        "genres": tag_caption(cap), "gender": detect_gender(cap)})
    os.makedirs(os.path.dirname(BANK_PATH), exist_ok=True)
    with open(BANK_PATH, "w", encoding="utf-8") as f:
        json.dump({"source": "ace-step/ACE-Step-1.5 examples/text2music",
                   "license": "MIT", "entries": entries}, f, ensure_ascii=False, indent=1)
    covered = {g for e in entries for g in e["genres"]}
    print(f"{len(entries)} entries -> {BANK_PATH}")
    print(f"genres covered {len(covered)}/{len(UI_GENRES)}; "
          f"missing: {sorted(set(UI_GENRES) - covered)}")


if __name__ == "__main__":
    default = os.path.join(config.ACESTEP_PROJECT_ROOT, "examples", "text2music")
    main(sys.argv[1] if len(sys.argv) > 1 else default)
```

生成数据：

```bash
.venv/bin/python scripts/build_caption_bank.py
```

Expected: `197 entries`（含中文的 3 条被跳过）；`genres covered 13/14; missing: ['hiphop.boom_bap']`（官方示例里没有 "boom bap" 字样，走 `preset.examples` 兜底，属预期）。

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_caption_bank.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add src/caption_bank.py scripts/build_caption_bank.py src/data/caption_bank.json tests/test_caption_bank.py
git commit -m "feat: 官方 caption 示例库(按曲风/性别检索,无示例回退 preset)"
```

---

### Task 7: planner 改为硬约束 + 示例检索 + caption 校验与重试

**Files:**
- Modify: `src/spec.py`
- Modify: `src/planner.py`
- Test: `tests/test_spec.py`、`tests/test_planner.py`（全文替换）

**Interfaces:**
- Consumes: `StyleDraw`、`sample_style`、`Locks`、`pick_examples`、`get_timbre`。
- Produces:
  - `VocalSpec.timbre: str = ""`；`SongSpec.style_draw: dict | None = None`（存 `StyleDraw.model_dump()`）；
  - `check_caption(caption: str, preset: Preset, timbre: VocalTimbre | None) -> str | None`；
  - `skeleton_spec(preset, draw: StyleDraw | None = None) -> SongSpec`；
  - `plan_song(style_desc, lyrics_hint="", *, preset=None, draw=None, llm_options=None, status_events=None) -> SongSpec`（`draw=None` 时用 `sample_style(preset, seed=0)`）。
  - 失败原因新增 `missing_genre` / `missing_timbre` / `conflict`。

- [ ] **Step 1: Write the failing test**

`tests/test_spec.py` 末尾追加：

```python
def test_vocal_timbre_and_style_draw_default_for_old_spec_json():
    old = SongSpec.model_validate_json('{"language": "zh", "vocal": {"gender": "male", "style": "x"}}')
    assert old.vocal.timbre == "" and old.style_draw is None


def test_style_draw_round_trips():
    s = SongSpec(style_draw={"preset_id": "rock.band", "bpm": 120})
    assert SongSpec.model_validate_json(s.model_dump_json()).style_draw["bpm"] == 120
```

`tests/test_planner.py` 全文替换为：

```python
import json
import pytest
from src import planner
from src.presets import UI_GENRES, get_preset
from src.spec import SongSpec
from src.style_sampler import Locks, StyleDraw, sample_style
from src.vocal_timbres import get_timbre

DRAW = StyleDraw(
    preset_id="hiphop.boom_bap",
    instruments=["jazzy piano sample", "dusty drum break", "upright bass"],
    textures=["warm"], era="90s", moods=["nocturnal"],
    vocal_timbre="rap_laidback", vocal_gender="male", bpm=88, seed=1,
)
BOOM = get_preset("hiphop.boom_bap")
CAPTION = ("A warm 90s boom bap hip-hop track with a laid-back, relaxed male rap flow over "
           "jazzy piano samples, a dusty drum break and upright bass.")
GOOD = {
    "language": "zh",
    "vocal": {"gender": "female", "style": "whatever"},     # 会被 draw 覆盖
    "genre": ["jazz"], "mood": ["happy"], "instrument": ["kazoo"], "bpm": 150,
    "keyscale": "F minor", "timesignature": 4,
    "structure": ["Intro", "Verse", "Hook", "Verse", "Hook", "Outro"],
    "caption": CAPTION,
}


def _llm(monkeypatch, *outputs):
    """按顺序返回 outputs,记录每次调用的 prompt 与 kwargs。"""
    calls = []
    seq = list(outputs)

    def fake(prompt, **k):
        calls.append({"prompt": prompt, **k})
        out = seq.pop(0) if len(seq) > 1 else seq[0]
        if isinstance(out, Exception):
            raise out
        return out
    monkeypatch.setattr(planner.llm, "complete", fake)
    return calls


def _plan(**kw):
    return planner.plan_song("说唱", preset=BOOM, draw=DRAW, **kw)


def test_draw_overrides_llm_choices(monkeypatch):
    _llm(monkeypatch, json.dumps(GOOD))
    events = []
    spec = _plan(status_events=events)
    assert isinstance(spec, SongSpec)
    assert events == [{"stage": "歌曲规划", "ok": True}]
    assert spec.caption == CAPTION and spec.caption_full is True
    assert spec.instrument == DRAW.instruments and spec.mood == ["nocturnal"]
    assert spec.bpm == 88 and spec.genre == ["hip hop", "boom bap"]
    assert spec.vocal.gender == "male" and spec.vocal.timbre == "rap_laidback"
    assert spec.vocal.style == "laid-back, relaxed rap flow"
    assert spec.keyscale == "F minor" and spec.preset_id == "hiphop.boom_bap"
    assert spec.style_draw == DRAW.model_dump()


def test_json_in_code_fence(monkeypatch):
    fence = "`" * 3      # 不在源码里直接写三个反引号,免得破坏 markdown 代码块
    _llm(monkeypatch, f"{fence}json\n{json.dumps(GOOD)}\n{fence}")
    assert _plan().caption_full is True


def test_mixed_language_normalized_to_policy(monkeypatch):
    _llm(monkeypatch, json.dumps(dict(GOOD, language="zh-en")))
    assert _plan().language == "zh"


def test_prompt_carries_hard_constraints_and_examples(monkeypatch):
    calls = _llm(monkeypatch, json.dumps(GOOD))
    _plan()
    p = calls[0]["prompt"]
    for s in ["jazzy piano sample", "dusty drum break", "upright bass", "warm", "90s",
              "nocturnal", "male laid-back, relaxed rap flow", "88 BPM", "boom bap",
              "supersaw", "硬性要求", "不得出现中文"]:
        assert s in p, s
    assert "官方风格 caption 示例" in p and "\n  - " in p


def test_empty_feeling_is_marked_in_prompt(monkeypatch):
    calls = _llm(monkeypatch, json.dumps(GOOD))
    planner.plan_song("", preset=BOOM, draw=DRAW)
    assert "未填写" in calls[0]["prompt"]


def test_missing_genre_retries_once_with_hint_then_succeeds(monkeypatch):
    bad = dict(GOOD, caption="A warm track with a laid-back, relaxed male rap flow.")
    calls = _llm(monkeypatch, json.dumps(bad), json.dumps(GOOD))
    events = []
    spec = _plan(status_events=events)
    assert len(calls) == 2 and "上一次输出不合格" in calls[1]["prompt"]
    assert "boom bap" in calls[1]["prompt"]
    assert spec.caption == CAPTION and events == [{"stage": "歌曲规划", "ok": True}]


@pytest.mark.parametrize("caption,reason", [
    ("A warm 90s boom bap track with a male rap verse.", "missing_timbre"),
    ("A boom bap track, laid-back rap flow, supersaw leads.", "conflict"),
    ("A smooth track with a laid-back rap flow.", "missing_genre"),
])
def test_two_bad_captions_fall_back_to_skeleton(monkeypatch, caption, reason):
    calls = _llm(monkeypatch, json.dumps(dict(GOOD, caption=caption)))
    events = []
    spec = _plan(status_events=events)
    assert len(calls) == 2
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": reason}]
    assert spec.caption_full is False and "jazzy piano sample" in spec.caption
    assert spec.bpm == 88 and spec.style_draw == DRAW.model_dump()


def test_cjk_falls_back_without_retry(monkeypatch):
    calls = _llm(monkeypatch, json.dumps(dict(GOOD, caption="中文 caption")))
    events = []
    spec = _plan(status_events=events)
    assert len(calls) == 1
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "non_english"}]
    assert "Hook" in spec.structure and spec.vocal.gender == "male"


def test_bad_json_falls_back(monkeypatch):
    _llm(monkeypatch, "抱歉我不会")
    events = []
    _plan(status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "bad_json"}]


def test_exception_falls_back_without_leaking(monkeypatch):
    _llm(monkeypatch, RuntimeError("bad key sk-SECRET"))
    events = []
    spec = _plan(status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "llm_error"}]
    assert spec.language == "zh"


def test_invalid_spec_reason(monkeypatch):
    _llm(monkeypatch, json.dumps(dict(GOOD, timesignature=5)))
    events = []
    _plan(status_events=events)
    assert events == [{"stage": "歌曲规划", "ok": False, "reason": "invalid_spec"}]


def test_passes_llm_options(monkeypatch):
    calls = _llm(monkeypatch, json.dumps(GOOD))
    _plan(llm_options={"provider": "deepseek", "model": "custom", "api_key": "k"})
    assert calls[0]["provider"] == "deepseek" and calls[0]["model"] == "custom"


def test_fusion_line_and_partner_genre(monkeypatch):
    draw = DRAW.model_copy(update={"fusion_id": "jazz.lounge",
                                   "instruments": [*DRAW.instruments, "muted trumpet"]})
    calls = _llm(monkeypatch, json.dumps(GOOD))
    spec = planner.plan_song("说唱", preset=BOOM, draw=draw)
    assert "编曲演进" in calls[0]["prompt"] and "爵士" in calls[0]["prompt"]
    assert "muted trumpet" in calls[0]["prompt"]
    assert spec.genre == ["hip hop", "boom bap", "jazz"]


def test_draw_defaults_to_seed_zero_sample(monkeypatch):
    calls = _llm(monkeypatch, "not json")
    spec = planner.plan_song("说唱", preset=BOOM)
    assert spec.style_draw == sample_style(BOOM, seed=0).model_dump()
    assert len(calls) == 1


def test_check_caption_reasons():
    t = get_timbre("rap_laidback")
    assert planner.check_caption(CAPTION, BOOM, t) is None
    assert planner.check_caption("中文", BOOM, t) == "non_english"
    assert planner.check_caption("laid-back rap", BOOM, t) == "missing_genre"
    assert planner.check_caption("Boom Bap rap", BOOM, t) == "missing_timbre"   # 大小写不敏感
    assert planner.check_caption("boom bap laid-back supersaw", BOOM, t) == "conflict"
    assert planner.check_caption("anything", get_preset("generic"), None) is None


@pytest.mark.parametrize("pid", UI_GENRES)
def test_skeleton_passes_its_own_check_for_every_timbre(pid):
    p = get_preset(pid)
    for tid in p.vocal_timbres:
        d = sample_style(p, seed=3, locks=Locks(vocal_timbre=tid))
        spec = planner.skeleton_spec(p, d)
        assert spec.caption_full is False and spec.bpm == d.bpm
        assert planner.check_caption(spec.caption, p, get_timbre(tid)) is None, spec.caption
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_spec.py tests/test_planner.py -q`
Expected: FAIL（`VocalSpec` 无 `timbre`；`plan_song() got an unexpected keyword argument 'draw'`）

- [ ] **Step 3: Write minimal implementation**

`src/spec.py`：

```python
class VocalSpec(BaseModel):
    gender: str = "female"
    style: str = "soft"
    timbre: str = ""      # 音色 id(src/vocal_timbres.py);老数据为空
```

`SongSpec` 在 `preset_id` 之后加：

```python
    # 本次风格采样结果(StyleDraw.model_dump());用于复现、展示与防重复。老数据为 None
    style_draw: dict | None = None
```

`src/planner.py` 全文替换为：

```python
import json
import logging
import random
import re

from src import llm
from src.caption_bank import pick_examples
from src.presets import Preset, get_preset
from src.spec import SongSpec, VocalSpec, parse_spec
from src.style_sampler import StyleDraw, sample_style
from src.textcheck import has_cjk, normalize_language
from src.vocal_timbres import VocalTimbre, get_timbre

_SYSTEM = (
    "你是音乐制作人。根据用户对歌曲感觉的描述和给定的硬性要求,只输出一个 JSON 对象,不要多余文字。"
    "caption 与所有英文字段必须是英文,不得出现中文。"
)

_TEMPLATE = """用户想要的感觉:{style}
{hint}
硬性要求(必须全部体现在 caption 中,不得替换或遗漏):
- 曲风:{label}(caption 必须包含以下词之一:{genre_words})
- 乐器:{instruments}
- 质感:{textures};年代/制作:{era}
- 情绪:{moods}
- 人声:{gender} {vocal}
- 速度:{bpm} BPM
{fusion}- 禁止出现的词:{avoid}
参考:
- caption 句式骨架(可改写,须保持自然语言整句):{skeleton}
- 调性倾向:{keyscale_hint}
- 结构模板:{structure}
- 官方风格 caption 示例(学习句式与维度,不要照抄):
{examples}

请输出 JSON,字段:
language(zh/en/yue/unknown), keyscale(如 "F minor"), timesignature(2/3/4/6),
structure(数组), caption(1-3 句英文,覆盖上面全部硬性要求,并尽量覆盖
风格/情绪/乐器/质感/年代/制作/人声/速度/结构 九个维度,不超过 400 字符)。
所有字段不得出现中文。只输出 JSON。"""

_FUSION_LINE = "- 编曲演进:以{label}开始,后段逐渐融入{partner}的元素({instruments})\n"

_HINTS = {
    "missing_genre": "caption 缺少曲风词,必须包含其中之一:{genre_words}",
    "missing_timbre": "caption 缺少人声音色描述,必须包含其中之一:{timbre_words}",
    "conflict": "caption 出现了禁止的词:{avoid}",
}


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


def check_caption(caption: str, preset: Preset, timbre: VocalTimbre | None) -> str | None:
    """返回不合格原因;合格返回 None。匹配不区分大小写。"""
    if has_cjk(caption):
        return "non_english"
    c = caption.lower()
    if preset.caption_keywords and not any(k in c for k in preset.caption_keywords):
        return "missing_genre"
    if timbre and not any(k in c for k in timbre.keywords):
        return "missing_timbre"
    if any(a.lower() in c for a in preset.avoid):
        return "conflict"
    return None


def _genres(preset: Preset, draw: StyleDraw) -> list[str]:
    tags = list(preset.genre_tags)
    if draw.fusion_id:
        tags += [t for t in get_preset(draw.fusion_id).genre_tags if t not in tags]
    return tags or ["pop"]


def _vocal_phrase(draw: StyleDraw, timbre: VocalTimbre | None) -> str:
    return f"{draw.vocal_gender} {timbre.caption if timbre else 'vocal'}"


def skeleton_spec(preset: Preset, draw: StyleDraw | None = None) -> SongSpec:
    """planner 降级时的 spec:用采样结果渲染 preset 骨架,降级也保留多样性。"""
    draw = draw or sample_style(preset, seed=0)
    timbre = get_timbre(draw.vocal_timbre)
    return SongSpec(
        language=preset.acestep.vocal_language_policy,
        vocal=VocalSpec(gender=draw.vocal_gender,
                        style=timbre.caption if timbre else "soft",
                        timbre=draw.vocal_timbre),
        genre=_genres(preset, draw),
        mood=draw.moods or ["neutral"],
        instrument=draw.instruments or ["drums", "bass", "keys"],
        bpm=draw.bpm,
        structure=list(preset.structure),
        caption=preset.render_skeleton(
            instruments=draw.instruments or None, textures=draw.textures or None,
            era=draw.era, vocal=_vocal_phrase(draw, timbre)),
        caption_full=False,
        keyscale="",
        timesignature=preset.timesignature,
        preset_id=preset.id,
        style_draw=draw.model_dump(),
    )


def _build_prompt(style_desc: str, lyrics_hint: str, preset: Preset, draw: StyleDraw,
                  timbre: VocalTimbre | None) -> str:
    rng = random.Random(draw.seed)
    examples = pick_examples(preset.id, draw.vocal_gender, rng, k=2)
    fusion = ""
    if draw.fusion_id:
        partner = get_preset(draw.fusion_id)
        own = set(preset.instrument_pool)
        borrowed = [i for i in draw.instruments if i not in own]
        fusion = _FUSION_LINE.format(label=preset.label, partner=partner.label,
                                     instruments=", ".join(borrowed) or "signature sounds")
        examples += pick_examples(partner.id, draw.vocal_gender, rng, k=1)
    return _TEMPLATE.format(
        style=style_desc.strip() or "(未填写,按硬性要求发挥)",
        hint=f"歌词片段参考:{lyrics_hint}" if lyrics_hint else "",
        label=preset.label,
        genre_words=", ".join(preset.caption_keywords[:2]) or "(不限)",
        instruments=", ".join(draw.instruments) or "(不限)",
        textures=", ".join(draw.textures) or "(不限)",
        era=draw.era,
        moods=", ".join(draw.moods) or "(不限)",
        gender=draw.vocal_gender,
        vocal=timbre.caption if timbre else "vocal",
        bpm=draw.bpm,
        fusion=fusion,
        avoid=", ".join(preset.avoid) or "(无)",
        skeleton=preset.caption_skeleton,
        keyscale_hint=preset.keyscale_hint or "(不限)",
        structure=" / ".join(preset.structure),
        examples="\n".join(f"  - {e}" for e in examples) or "  (无)",
    )


def _hint(reason: str, preset: Preset, timbre: VocalTimbre | None) -> str:
    return _HINTS[reason].format(
        genre_words=", ".join(preset.caption_keywords),
        timbre_words=", ".join(timbre.keywords) if timbre else "",
        avoid=", ".join(preset.avoid),
    )


def _apply_draw(data: dict, preset: Preset, draw: StyleDraw,
                timbre: VocalTimbre | None) -> None:
    """采样器是要素的唯一来源:LLM 给的 genre/mood/instrument/bpm/vocal 一律覆盖。"""
    data["genre"] = _genres(preset, draw)
    if draw.moods:
        data["mood"] = list(draw.moods)
    if draw.instruments:
        data["instrument"] = list(draw.instruments)
    data["bpm"] = draw.bpm
    data["vocal"] = {"gender": draw.vocal_gender,
                     "style": timbre.caption if timbre else "soft",
                     "timbre": draw.vocal_timbre}
    data["style_draw"] = draw.model_dump()


def plan_song(
    style_desc: str,
    lyrics_hint: str = "",
    *,
    preset: Preset | None = None,
    draw: StyleDraw | None = None,
    llm_options: dict | None = None,
    status_events: list[dict] | None = None,
) -> SongSpec:
    preset = preset or get_preset("")
    draw = draw or sample_style(preset, seed=0)
    timbre = get_timbre(draw.vocal_timbre)
    prompt = _build_prompt(style_desc, lyrics_hint, preset, draw, timbre)
    reason: str | None = None
    for _attempt in range(2):        # 只有 caption 校验失败才会进入第二轮
        try:
            raw = llm.complete(prompt, system=_SYSTEM, **(llm_options or {}))
        except Exception as e:  # noqa: BLE001 — 事件里不带异常原文
            logging.warning("planner LLM failed, using preset skeleton: %s", type(e).__name__)
            reason = "llm_error"
            break
        try:
            data = _extract_json(raw)
        except (ValueError, json.JSONDecodeError):
            reason = "bad_json"
            break
        data["language"] = normalize_language(
            str(data.get("language", "")), preset.acestep.vocal_language_policy)
        data["preset_id"] = preset.id
        data["caption_full"] = bool(str(data.get("caption", "")).strip())
        _apply_draw(data, preset, draw, timbre)
        try:
            spec = parse_spec(data)
        except ValueError as e:
            reason = "non_english" if "CJK" in str(e) else "invalid_spec"
            logging.warning("planner output rejected (%s), using preset skeleton", reason)
            break
        reason = check_caption(spec.caption, preset, timbre)
        if reason is None:
            _emit(status_events, True, None)
            return spec
        prompt += f"\n\n上一次输出不合格:{_hint(reason, preset, timbre)}。请重新输出完整 JSON。"
    _emit(status_events, False, reason)
    return skeleton_spec(preset, draw)
```

注意：`parse_spec` 遇到 caption 含中文时报的是 `must not contain CJK characters`，所以 `test_cjk_falls_back_without_retry` 走 `non_english` 且只调 1 次。

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_spec.py tests/test_planner.py -q`
Expected: 全部通过。

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: `test_pipeline.py` 中依赖旧行为的用例会失败（genre 事后覆盖、事件数量），Task 9 重写；其余通过。**本任务提交前确认失败只出现在 `test_pipeline.py`。**

- [ ] **Step 5: Commit**

```bash
git add src/spec.py src/planner.py tests/test_spec.py tests/test_planner.py
git commit -m "feat: planner 以采样结果为硬约束,检索官方示例,caption 校验+重试+按采样渲染骨架"
```

---

### Task 8: 歌词段落标签按音色加修饰

**Files:**
- Modify: `src/lyric_text.py`
- Modify: `src/lyrics.py`
- Test: `tests/test_lyric_text.py`、`tests/test_lyrics.py`

**Interfaces:**
- Produces: `apply_structure_tags(text, structure, vocal_qualifier="", section_tags=None)`；`section_tags: dict[str, str]`，键按标签名前缀匹配（不区分大小写），只改不含 `-` 的标签；合并顺序 `{"Verse": vocal_qualifier, **section_tags}`（音色优先）。`structure_lyrics` 从 `spec.vocal.timbre` 取音色的 `section_tags`。

- [ ] **Step 1: Write the failing test**

`tests/test_lyric_text.py` 末尾追加：

```python
def test_section_tags_qualify_chorus_and_skip_tags_with_dash():
    text = "[Verse]\n甲\n\n[Pre-Chorus]\n乙\n\n[Chorus]\n丙\n\n[Chorus 2]\n丁"
    out = apply_structure_tags(text, STRUCT, section_tags={"Chorus": "powerful"})
    assert "[Chorus - powerful]" in out and "[Chorus 2 - powerful]" in out
    assert "[Pre-Chorus]" in out and "[Verse]\n" in out


def test_timbre_section_tags_win_over_vocal_qualifier():
    out = apply_structure_tags("[Verse]\n甲\n\n[Hook]\n乙", STRUCT,
                               vocal_qualifier="rap", section_tags={"Verse": "breathy"})
    assert "[Verse - breathy]" in out and "[Hook]" in out
```

`tests/test_lyrics.py` 末尾追加：

```python
def test_timbre_section_tags_applied(monkeypatch):
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "")
    spec = safe_spec()
    spec.vocal.timbre = "powerful"
    out = lyrics.structure_lyrics("[Verse]\n甲乙\n\n[Chorus]\n丙丁", spec)
    assert "[Chorus - powerful]" in out and "[Verse]" in out


def test_unknown_timbre_in_old_spec_is_ignored(monkeypatch):
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "")
    spec = safe_spec()
    spec.vocal.timbre = "robot"
    out = lyrics.structure_lyrics("[Chorus]\n丙丁", spec)
    assert "[Chorus]" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_lyric_text.py tests/test_lyrics.py -q`
Expected: FAIL with `TypeError: apply_structure_tags() got an unexpected keyword argument 'section_tags'`

- [ ] **Step 3: Write minimal implementation**

`src/lyric_text.py`：删除 `_VERSE_TAG` 与 `_qualify_verse`，加入：

```python
# 不含 "-" 的整行标签才会被加修饰:[Pre-Chorus]、[Verse - whispered] 原样保留
_PLAIN_TAG = re.compile(r"^\s*\[([^\]\-]+)\]\s*$")


def _qualify(line: str, section_tags: dict[str, str]) -> str:
    m = _PLAIN_TAG.match(line)
    if not m:
        return line
    name = m.group(1).strip()
    for key, mod in section_tags.items():
        if name.lower().startswith(key.lower()):
            return f"[{name} - {mod}]"
    return line
```

`apply_structure_tags` 签名与结尾改为：

```python
def apply_structure_tags(text: str, structure: list[str], vocal_qualifier: str = "",
                         section_tags: dict[str, str] | None = None) -> str:
    """用户已有标签 → 全部保留;无 → 按 structure 中的人声段顺序补;再按段落加修饰。

    修饰来源:preset 的 vocal_qualifier(只作用于 Verse)与音色的 section_tags,后者优先。
    """
    # …… 中间补标签的逻辑不变 ……
    tags = {"Verse": vocal_qualifier} if vocal_qualifier else {}
    tags.update(section_tags or {})
    if tags:
        tagged = [_qualify(l, tags) for l in tagged]
    return "\n".join(tagged)
```

`src/lyrics.py`：import 加 `from src.vocal_timbres import get_timbre`，`structure_lyrics` 末尾的 `apply_structure_tags(...)` 一行改为：

```python
    try:
        timbre = get_timbre(spec.vocal.timbre)
    except ValueError:      # 老数据里的未知音色:不加修饰
        timbre = None
    text = apply_structure_tags(text, spec.structure or preset.structure,
                                preset.vocal_qualifier,
                                timbre.section_tags if timbre else None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_lyric_text.py tests/test_lyrics.py -q`
Expected: 全部通过（含原有 `test_apply_structure_tags_qualifies_verse_only`、`test_hiphop_preset_qualifies_verse_with_rap`）。

- [ ] **Step 5: Commit**

```bash
git add src/lyric_text.py src/lyrics.py tests/test_lyric_text.py tests/test_lyrics.py
git commit -m "feat: 歌词段落标签按人声音色加修饰(音色优先于 preset 限定词)"
```

---
### Task 9: 流水线串联（识别 → 采样 → 规划 → 歌词 → 出歌），seed 补全

**Files:**
- Modify: `src/pipeline.py`
- Test: `tests/test_pipeline.py`（全文替换）

**Interfaces:**
- Consumes: `resolve_genre`、`sample_style`、`Locks`、`parse_recent`、`planner.plan_song(…, draw=…)`。
- Produces: `make_song(raw_lyrics, style_desc, *, length="full", seed=None, work_dir=None, overrides=None, llm_options=None, recent=None) -> dict`，返回值新增 `"seed": int` 与 `"style_draw": StyleDraw`。`overrides` 识别的键：`preset` / `mood` / `vocal_gender` / `vocal_timbre` / `creativity` / `language`，以及兼容旧客户端的 `genre`（并入识别文本）。

- [ ] **Step 1: Write the failing test**

`tests/test_pipeline.py` 全文替换为：

```python
import json
import pytest
from src import pipeline
from src.presets import get_preset
from src.spec import SAFE_DEFAULT_SPEC, SongSpec


@pytest.fixture
def capture(monkeypatch):
    """替换 planner / lyrics / 出歌,记录各阶段收到的参数。"""
    seen: dict = {}

    def fake_plan(style, lyrics_hint="", *, preset=None, draw=None, llm_options=None,
                  status_events=None):
        seen.update(plan_preset=preset.id, draw=draw, plan_options=llm_options)
        status_events.append({"stage": "歌曲规划", "ok": True})
        return pipeline.planner.skeleton_spec(preset, draw)

    def fake_lyrics(raw, spec, *, preset=None, llm_options=None, status_events=None):
        seen["lyrics_preset"] = preset.id
        status_events.append({"stage": "歌词整理", "ok": True})
        return "[Verse]\n" + raw

    def fake_gen(structured, spec, *, length, seed, out_path):
        seen.update(gen_spec=spec, gen_seed=seed, length=length)
        return out_path

    monkeypatch.setattr(pipeline.planner, "plan_song", fake_plan)
    monkeypatch.setattr(pipeline.lyrics, "structure_lyrics", fake_lyrics)
    monkeypatch.setattr(pipeline.song_gen, "generate_song", fake_gen)
    return seen


def test_orchestrates_resolve_sample_plan_lyrics_gen(capture, tmp_path):
    result = pipeline.make_song("我的歌词", "女声 R&B", length="short", seed=42,
                                work_dir=str(tmp_path))
    assert capture["plan_preset"] == capture["lyrics_preset"] == "rnb.soul"
    assert capture["draw"].preset_id == "rnb.soul" and capture["draw"].seed == 42
    assert capture["gen_seed"] == 42 and result["seed"] == 42
    assert capture["length"] == "short"
    assert result["style_draw"] == capture["draw"]
    assert isinstance(result["spec"], SongSpec) and result["preset_id"] == "rnb.soul"
    assert result["llm_status"] == [
        {"stage": "曲风识别", "ok": True, "source": "keyword"},
        {"stage": "歌曲规划", "ok": True},
        {"stage": "歌词整理", "ok": True},
    ]
    assert result["degraded"] is False


def test_seed_generated_when_missing_and_shared(capture, tmp_path):
    result = pipeline.make_song("词", "摇滚", work_dir=str(tmp_path))
    assert isinstance(result["seed"], int) and 0 <= result["seed"] < 2**31
    assert capture["gen_seed"] == result["seed"] == capture["draw"].seed


def test_overrides_become_locks(capture, tmp_path):
    result = pipeline.make_song(
        "词", "随便", seed=3, work_dir=str(tmp_path),
        overrides={"preset": "rock.band", "mood": ["sad"], "vocal_gender": "female",
                   "vocal_timbre": "choir", "creativity": "pure", "language": "en"})
    d = capture["draw"]
    assert d.preset_id == "rock.band" and d.moods == ["sad"]
    assert d.vocal_gender == "female" and d.vocal_timbre == "choir"
    assert d.bpm == get_preset("rock.band").bpm_default()         # pure → typical
    assert result["spec"].language == "en"
    assert result["spec"].mood == ["sad"]                         # 不再事后覆盖,由 draw 带入


def test_legacy_genre_tag_feeds_detection(capture, tmp_path):
    pipeline.make_song("词", "", seed=1, work_dir=str(tmp_path),
                       overrides={"genre": ["jazz"]})
    assert capture["plan_preset"] == "jazz.lounge"


def test_recent_draws_steer_random_genre(capture, tmp_path):
    recent = [{"preset_id": pid, "instruments": ["x"], "textures": [], "era": "modern",
               "moods": [], "vocal_timbre": "clear", "vocal_gender": "female", "bpm": 100,
               "seed": 0} for pid in ("pop.ballad", "rock.band", "lofi.chill")]
    for s in range(30):
        pipeline.make_song("词", "", seed=s, work_dir=str(tmp_path),
                           recent=[*recent, {"garbage": True}])
        assert capture["plan_preset"] not in {"pop.ballad", "rock.band", "lofi.chill"}


def test_unknown_preset_raises(capture, tmp_path):
    with pytest.raises(ValueError):
        pipeline.make_song("词", "x", work_dir=str(tmp_path), overrides={"preset": "nope"})


def test_all_llm_failures_still_generate(monkeypatch, tmp_path):
    calls = []

    def fail(*a, **k):
        calls.append(k)
        raise RuntimeError("offline")
    monkeypatch.setattr(pipeline.planner.llm, "complete", fail)
    monkeypatch.setattr(pipeline.song_gen, "generate_song",
                        lambda structured, spec, **k: k["out_path"])
    options = {"provider": "gemini", "model": "gemini-test", "api_key": "k"}
    result = pipeline.make_song("词", "夏天的海边", length="short", work_dir=str(tmp_path),
                                llm_options=options)
    assert len(calls) == 3                         # 识别 / 规划 / 断行各一次
    assert all(c["provider"] == "gemini" for c in calls)
    assert result["llm_status"] == [
        {"stage": "曲风识别", "ok": False, "source": "random", "reason": "llm_error"},
        {"stage": "歌曲规划", "ok": False, "reason": "llm_error"},
        {"stage": "歌词整理", "ok": False, "reason": "llm_error"},
    ]
    assert result["degraded"] is True


def test_uses_configured_provider_by_default(monkeypatch, tmp_path):
    """调用方没指定供应商时,走 config.LLM_PROVIDER。"""
    monkeypatch.setattr(pipeline.config, "LLM_PROVIDER", "deepseek")
    seen = []
    monkeypatch.setattr(pipeline.planner.llm, "complete",
                        lambda *a, **k: seen.append(k) or json.dumps(SAFE_DEFAULT_SPEC))
    monkeypatch.setattr(pipeline.song_gen, "generate_song",
                        lambda structured, spec, **k: k["out_path"])
    pipeline.make_song("词", "女声 R&B", work_dir=str(tmp_path))
    assert seen and {k.get("provider") for k in seen} == {"deepseek"}


def test_explicit_llm_options_override_configured_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline.config, "LLM_PROVIDER", "deepseek")
    seen = []
    monkeypatch.setattr(pipeline.planner.llm, "complete",
                        lambda *a, **k: seen.append(k) or json.dumps(SAFE_DEFAULT_SPEC))
    monkeypatch.setattr(pipeline.song_gen, "generate_song",
                        lambda structured, spec, **k: k["out_path"])
    pipeline.make_song("词", "女声 R&B", work_dir=str(tmp_path),
                       llm_options={"provider": "gemini"})
    assert seen and {k.get("provider") for k in seen} == {"gemini"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_pipeline.py -q`
Expected: FAIL（`make_song() got an unexpected keyword argument 'recent'`、`KeyError: 'seed'` 等）

- [ ] **Step 3: Write minimal implementation**

`src/pipeline.py` 全文替换为：

```python
import os
import secrets

import config
from src import planner, lyrics, song_gen
from src.style_sampler import Locks, parse_recent, resolve_genre, sample_style


def make_song(raw_lyrics: str, style_desc: str, *,
              length: str = "full", seed: int | None = None,
              work_dir: str | None = None,
              overrides: dict | None = None,
              llm_options: dict | None = None,
              recent: list[dict] | None = None) -> dict:
    """识别曲风 → 采样要素 → 规划 caption → 整理歌词 → 出歌。

    recent:同一用户最近几首的 style_draw(新 → 旧),用于避开刚用过的曲风/乐器/音色。
    """
    out_dir = work_dir or config.OUTPUTS_DIR
    os.makedirs(out_dir, exist_ok=True)
    overrides = overrides or {}

    # 采样器与 DiT 共用同一个 seed;调用方没给就在这里生成,随结果返回以便落库复现。
    if seed is None:
        seed = secrets.randbelow(2**31)

    # 调用方没指定供应商时用配置值(而不是 llm.complete 签名里的默认值)。
    llm_options = {"provider": config.LLM_PROVIDER, **(llm_options or {})}
    recent_draws = parse_recent(recent or [])

    llm_status: list[dict] = []
    # 旧客户端可能仍发 genre tag:并入识别文本。用户选择一律在采样前作为锁定项进入,
    # 不再在 planner 之后覆盖 spec —— caption 写好后再改 genre 对 DiT 无效。
    feeling_text = " ".join([style_desc or "", *(overrides.get("genre") or [])]).strip()
    preset = resolve_genre(
        overrides.get("preset"), feeling_text, seed=seed,
        recent_ids=[d.preset_id for d in recent_draws],
        llm_options=llm_options, status_events=llm_status,
    )
    draw = sample_style(
        preset, seed=seed,
        locks=Locks(moods=overrides.get("mood") or [],
                    vocal_gender=overrides.get("vocal_gender") or "",
                    vocal_timbre=overrides.get("vocal_timbre") or ""),
        creativity=overrides.get("creativity") or "normal",
        recent=recent_draws,
    )
    spec = planner.plan_song(
        style_desc, lyrics_hint=raw_lyrics[:80], preset=preset, draw=draw,
        llm_options=llm_options, status_events=llm_status,
    )
    if overrides.get("language"):
        spec = spec.__class__(**{**spec.model_dump(), "language": overrides["language"]})
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
        "seed": seed,
        "style_draw": draw,
        "llm_status": llm_status,
        # 任一阶段回退即为降级生成 —— 由事件的 ok 位判定,不靠文案匹配。
        "degraded": any(not e["ok"] for e in llm_status),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: 流水线改为 识别→采样→规划→歌词→出歌;用户选择作为锁定项;seed 补全并返回"
```

---

### Task 10: 落库 seed 与读取最近采样（db + queue）

**Files:**
- Modify: `server/db.py`
- Modify: `server/queue.py`
- Test: `tests/test_db.py`、`tests/test_queue.py`

**Interfaces:**
- Produces: `db.recent_style_draws(created_by: str, limit: int = 5) -> list[dict]`（新 → 旧，跳过没有 `style_draw` 的老歌）；`run_generation` 把 `recent` 传给 `make_song`，落库 `seed = result["seed"]`。

- [ ] **Step 1: Write the failing test**

`tests/test_db.py` 末尾追加：

```python
def test_recent_style_draws_filters_user_and_skips_old_songs(tmp_path):
    import json
    import time
    from server import db
    db.init_db(str(tmp_path / "r.db"))
    rows = [("a", "ze", {"style_draw": {"preset_id": "rock.band"}}),
            ("b", "ze", {"language": "zh"}),                              # 老歌:没有 style_draw
            ("c", "other", {"style_draw": {"preset_id": "jazz.lounge"}}),
            ("d", "ze", {"style_draw": {"preset_id": "lofi.chill"}})]
    for sid, who, spec in rows:
        db.insert_song({"id": sid, "title": sid, "lyrics": "", "feeling": "",
                        "spec_json": json.dumps(spec), "structured_lyrics": "",
                        "seed": 1, "mp3_url": "", "duration_sec": 1.0,
                        "instrumental": 0, "created_by": who, "llm_status": "[]"})
        time.sleep(0.002)          # created_at 精确到微秒,留出间隔保证排序稳定
    got = db.recent_style_draws("ze", limit=5)
    assert [d["preset_id"] for d in got] == ["lofi.chill", "rock.band"]   # 新 → 旧
    assert db.recent_style_draws("ze", limit=1) == [{"preset_id": "lofi.chill"}]
```

`tests/test_queue.py`：在 `test_run_generation_orchestrates` 里补一行 patch（否则会去读真实数据库）：

```python
    monkeypatch.setattr(queue.db, "recent_style_draws", lambda who, limit=5: [])
```

并追加：

```python
def test_run_generation_passes_recent_and_saves_result_seed(monkeypatch, tmp_path):
    seen = {}

    def fake_make_song(*a, **k):
        seen.update(k)
        return {"song": str(tmp_path / "song.wav"), "spec": _FakeSpec(),
                "structured_lyrics": "x", "llm_status": [], "degraded": False, "seed": 42}
    monkeypatch.setattr(queue.pipeline, "make_song", fake_make_song)
    monkeypatch.setattr(queue.db, "recent_style_draws",
                        lambda who, limit=5: [{"preset_id": "rock.band"}] if who == "ze" else [])
    monkeypatch.setattr(queue.storage, "wav_to_mp3", lambda w, m: m)
    monkeypatch.setattr(queue.storage, "probe_duration", lambda p: 1.0)
    monkeypatch.setattr(queue.storage, "upload_to_r2", lambda p, key: key)
    saved = {}
    monkeypatch.setattr(queue.db, "insert_song", lambda s: saved.update(s))

    queue.run_generation("j1", {"lyrics": "词", "feeling": "", "seed": None,
                                "overrides": {}}, "ze")
    assert seen["recent"] == [{"preset_id": "rock.band"}]
    assert saved["seed"] == 42
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_db.py tests/test_queue.py -q`
Expected: FAIL with `AttributeError: module 'server.db' has no attribute 'recent_style_draws'`

- [ ] **Step 3: Write minimal implementation**

`server/db.py`：顶部加 `import json`，在 `list_songs` 之后加入：

```python
def recent_style_draws(created_by: str, limit: int = 5) -> list[dict]:
    """同一用户最近几首的风格采样结果(新 → 旧),给采样器防重复。老歌没有 style_draw,跳过。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT spec_json FROM songs WHERE created_by=? ORDER BY created_at DESC LIMIT ?",
            (created_by, limit),
        ).fetchall()
    out: list[dict] = []
    for r in rows:
        try:
            draw = json.loads(r["spec_json"] or "{}").get("style_draw")
        except (ValueError, AttributeError):
            continue
        if isinstance(draw, dict):
            out.append(draw)
    return out
```

`server/queue.py` 的 `run_generation`：

```python
    result = pipeline.make_song(
        payload["lyrics"], payload["feeling"],
        length=payload.get("length", "auto"),
        seed=payload.get("seed"),
        overrides=payload.get("overrides") or {},
        recent=db.recent_style_draws(created_by),
    )
```

以及 song 字典里的 seed：

```python
        # 流水线会在 seed 为空时生成一个;落库的是实际用的那个,才能复现
        "seed": result.get("seed", payload.get("seed")),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add server/db.py server/queue.py tests/test_db.py tests/test_queue.py
git commit -m "feat: 落库实际使用的 seed;按用户读取最近风格采样供防重复"
```

---

### Task 11: API — `vocal_timbre` / `creativity` 校验与 `GET /api/styles`

**Files:**
- Modify: `server/models.py`
- Modify: `server/routes.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces: `Overrides.vocal_timbre: str = ""`（空或已知 id，否则 422）；`Overrides.creativity: str = "normal"`（∈ `CREATIVITY_LEVELS`，否则 422）；`GET /api/styles` → `{"genres": [{"id","label","family"}], "timbres": [{"id","label"}], "creativity": [{"id","label"}]}`（不需要口令，与 `/api/inspirations` 一致）。

- [ ] **Step 1: Write the failing test**

`tests/test_api.py` 末尾追加：

```python
def test_generate_accepts_timbre_and_creativity(monkeypatch, tmp_path):
    captured = _with_fake_queue(monkeypatch, tmp_path, "t1.db")
    r = client.post("/api/generate", json=_body(overrides={
        "preset": "pop.city_pop", "vocal_timbre": "breathy", "creativity": "fusion"}))
    assert r.status_code == 200
    o = captured["overrides"]
    assert (o["preset"], o["vocal_timbre"], o["creativity"]) == \
        ("pop.city_pop", "breathy", "fusion")


def test_generate_defaults_creativity_to_normal(monkeypatch, tmp_path):
    captured = _with_fake_queue(monkeypatch, tmp_path, "t2.db")
    client.post("/api/generate", json=_body())
    assert captured["overrides"]["creativity"] == "normal"
    assert captured["overrides"]["vocal_timbre"] == ""


def test_generate_rejects_unknown_timbre_or_creativity(monkeypatch, tmp_path):
    _with_fake_queue(monkeypatch, tmp_path, "t3.db")
    assert client.post("/api/generate",
                       json=_body(overrides={"vocal_timbre": "robot"})).status_code == 422
    assert client.post("/api/generate",
                       json=_body(overrides={"creativity": "wild"})).status_code == 422


def test_styles_endpoint():
    body = client.get("/api/styles").json()
    ids = [g["id"] for g in body["genres"]]
    assert len(ids) == 14 and ids[0] == "pop.ballad" and "generic" not in ids
    assert {"id", "label", "family"} <= set(body["genres"][0])
    assert [t["id"] for t in body["timbres"]][:2] == ["clear", "breathy"]
    assert [c["id"] for c in body["creativity"]] == ["pure", "normal", "fusion"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api.py -q`
Expected: FAIL（`vocal_timbre` 未透传；`/api/styles` 404）

- [ ] **Step 3: Write minimal implementation**

`server/models.py`：import 增加

```python
from src.style_sampler import CREATIVITY_LEVELS
from src.vocal_timbres import get_timbre
```

`Overrides` 增加字段与校验：

```python
    # 人声音色 id;空 → 由采样器按曲风挑
    vocal_timbre: str = ""
    # 创意度:pure 纯正 / normal 常规 / fusion 融合
    creativity: str = "normal"

    @field_validator("vocal_timbre")
    @classmethod
    def _known_timbre(cls, v: str) -> str:
        get_timbre(v)  # 未知 id 抛 ValueError → 422
        return v

    @field_validator("creativity")
    @classmethod
    def _known_creativity(cls, v: str) -> str:
        if v not in CREATIVITY_LEVELS:
            raise ValueError(f"creativity must be one of {CREATIVITY_LEVELS}")
        return v
```

`server/routes.py`：import 增加

```python
from src.presets import PRESETS, UI_GENRES
from src.vocal_timbres import TIMBRES
```

文件末尾加：

```python
_CREATIVITY_LABELS = [("pure", "纯正"), ("normal", "常规"), ("fusion", "融合")]


@router.get("/styles")
def get_styles():
    """曲风 / 音色 / 创意度的选项与中文名。前端据此渲染,避免两端数据不同步。"""
    return {
        "genres": [{"id": pid, "label": PRESETS[pid].label, "family": PRESETS[pid].family}
                   for pid in UI_GENRES],
        "timbres": [{"id": t.id, "label": t.label} for t in TIMBRES.values()],
        "creativity": [{"id": i, "label": l} for i, l in _CREATIVITY_LABELS],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add server/models.py server/routes.py tests/test_api.py
git commit -m "feat(api): 人声音色/创意度参数校验,新增 GET /api/styles"
```

---
### Task 12: 前端数据层 — 类型、`getStyles`、`useStyles`、`styleSummary`

**Files:**
- Modify: `web/lib/types.ts`
- Modify: `web/lib/api.ts`
- Create: `web/lib/styles.ts`
- Test: `web/test/styles.test.ts`

**Interfaces:**
- Produces:
  - `StyleOption { id: string; label: string; family?: string }`、`Styles { genres; timbres; creativity }`、`Creativity = "pure" | "normal" | "fusion"`；`GenerateInput.overrides` 增加 `vocal_timbre?: string`、`creativity?: Creativity`；
  - `getStyles(): Promise<Styles>`；
  - `loadStyles()`（模块级缓存，失败清缓存）、`resetStylesCache()`（测试用）、`useStyles(): Styles | null`；
  - `styleSummary(specJson, styles): string | null`，如 `"City Pop × 爵士 · 气声女声 · 108 BPM"`；没有 `style_draw` 或 JSON 坏掉返回 `null`；`styles` 为空时退回 id。

- [ ] **Step 1: Write the failing test**

```ts
// web/test/styles.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest"
import { styleSummary, loadStyles, resetStylesCache } from "@/lib/styles"
import { getStyles } from "@/lib/api"
import type { Styles } from "@/lib/types"

vi.mock("@/lib/api", () => ({ getStyles: vi.fn() }))

const STYLES: Styles = {
  genres: [
    { id: "pop.city_pop", label: "City Pop", family: "pop" },
    { id: "jazz.lounge", label: "爵士", family: "chill" },
  ],
  timbres: [{ id: "breathy", label: "气声" }],
  creativity: [{ id: "normal", label: "常规" }],
}

const spec = (draw: object | null) =>
  JSON.stringify({ vocal: { gender: "female" }, style_draw: draw })

const DRAW = {
  preset_id: "pop.city_pop", vocal_timbre: "breathy", vocal_gender: "female", bpm: 108,
  fusion_id: null,
}

describe("styleSummary", () => {
  it("拼出 曲风 · 音色+性别 · BPM", () => {
    expect(styleSummary(spec(DRAW), STYLES)).toBe("City Pop · 气声女声 · 108 BPM")
  })
  it("融合档显示伙伴曲风", () => {
    expect(styleSummary(spec({ ...DRAW, fusion_id: "jazz.lounge" }), STYLES)).toBe(
      "City Pop × 爵士 · 气声女声 · 108 BPM",
    )
  })
  it("没有选项列表时退回 id", () => {
    expect(styleSummary(spec({ ...DRAW, vocal_gender: "male" }), null)).toBe(
      "pop.city_pop · breathy男声 · 108 BPM",
    )
  })
  it("老歌没有 style_draw 或 JSON 坏掉返回 null", () => {
    expect(styleSummary(spec(null), STYLES)).toBeNull()
    expect(styleSummary("{bad", STYLES)).toBeNull()
    expect(styleSummary("", STYLES)).toBeNull()
  })
})

describe("loadStyles", () => {
  beforeEach(() => {
    resetStylesCache()
    vi.mocked(getStyles).mockReset()
  })
  it("只请求一次", async () => {
    vi.mocked(getStyles).mockResolvedValue(STYLES)
    await loadStyles()
    await loadStyles()
    expect(getStyles).toHaveBeenCalledTimes(1)
  })
  it("失败后清缓存,下次重试", async () => {
    vi.mocked(getStyles).mockRejectedValueOnce(new Error("x")).mockResolvedValue(STYLES)
    await expect(loadStyles()).rejects.toThrow()
    await expect(loadStyles()).resolves.toEqual(STYLES)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run test/styles.test.ts`
Expected: FAIL（`Failed to resolve import "@/lib/styles"`）

- [ ] **Step 3: Write minimal implementation**

`web/lib/types.ts`：`GenerateInput.overrides` 改为

```ts
  overrides: {
    genre?: string[]
    mood?: string[]
    vocal_gender?: string
    language?: string
    preset?: string
    /** 人声音色 id;空 = 由后端按曲风挑 */
    vocal_timbre?: string
    creativity?: Creativity
  }
```

文件末尾追加：

```ts
export type Creativity = "pure" | "normal" | "fusion"

/** 曲风 / 音色 / 创意度的一个选项;family 只有曲风有,用于分组 */
export interface StyleOption {
  id: string
  label: string
  family?: string
}

/** GET /api/styles 的返回 */
export interface Styles {
  genres: StyleOption[]
  timbres: StyleOption[]
  creativity: StyleOption[]
}
```

`web/lib/api.ts`：import 加 `Styles`，末尾追加：

```ts
export function getStyles() {
  return req<Styles>("/api/styles")
}
```

```ts
// web/lib/styles.ts
"use client"
import { useEffect, useState } from "react"
import { getStyles } from "./api"
import type { Styles } from "./types"

let cache: Promise<Styles> | null = null

/** 曲风/音色列表整个页面只拉一次;失败时清掉缓存,下次重试。 */
export function loadStyles(): Promise<Styles> {
  if (!cache) {
    // 包一层 Promise:getStyles 同步抛错(如测试里 mock 被还原)也走 reject,不炸组件
    cache = Promise.resolve()
      .then(() => getStyles())
      .catch((e) => {
        cache = null
        throw e
      })
  }
  return cache
}

/** 测试用 */
export function resetStylesCache() {
  cache = null
}

export function useStyles(): Styles | null {
  const [styles, setStyles] = useState<Styles | null>(null)
  useEffect(() => {
    let alive = true
    loadStyles()
      .then((s) => alive && setStyles(s))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])
  return styles
}

const GENDER_LABEL: Record<string, string> = { female: "女声", male: "男声" }

/** 歌曲卡片上的风格摘要,如「City Pop · 气声女声 · 108 BPM」。老歌(无 style_draw)返回 null。 */
export function styleSummary(
  specJson: string | null | undefined,
  styles: Styles | null,
): string | null {
  if (!specJson) return null
  let draw
  try {
    draw = JSON.parse(specJson)?.style_draw
  } catch {
    return null
  }
  if (!draw || typeof draw !== "object") return null
  const name = (list: { id: string; label: string }[] | undefined, id: string) =>
    list?.find((o) => o.id === id)?.label ?? id
  const genre = name(styles?.genres, draw.preset_id)
  const fusion = draw.fusion_id ? ` × ${name(styles?.genres, draw.fusion_id)}` : ""
  const timbre = name(styles?.timbres, draw.vocal_timbre)
  const gender = GENDER_LABEL[draw.vocal_gender] ?? ""
  return `${genre}${fusion} · ${timbre}${gender} · ${draw.bpm} BPM`
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run test/styles.test.ts && npx tsc --noEmit`
Expected: `6 passed`；tsc 无输出。

- [ ] **Step 5: Commit**

```bash
git add web/lib/types.ts web/lib/api.ts web/lib/styles.ts web/test/styles.test.ts
git commit -m "feat(web): 风格选项类型/接口/缓存 hook 与风格摘要"
```

---

### Task 13: 生成表单 — 曲风网格、人声音色、创意度

**Files:**
- Modify: `web/components/AdvancedSettings.tsx`（全文替换）
- Modify: `web/components/GenerateForm.tsx`
- Test: `web/test/AdvancedSettings.test.tsx`（全文替换）、`web/test/GenerateForm.test.tsx`

**Interfaces:**
- Produces: `AdvValue = { mood: string[]; vocal_gender: string; language: string; preset: string; vocal_timbre: string; creativity: Creativity }`（去掉 `genre`）；`AdvancedSettings({ value, onChange, styles })`。`GenerateForm` 提交 `overrides = { preset, mood, vocal_gender, language, vocal_timbre, creativity }`。

- [ ] **Step 1: Write the failing test**

`web/test/AdvancedSettings.test.tsx` 全文替换为：

```tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import AdvancedSettings, { type AdvValue } from "@/components/AdvancedSettings"
import type { Styles } from "@/lib/types"

const STYLES: Styles = {
  genres: [
    { id: "pop.ballad", label: "流行抒情", family: "pop" },
    { id: "pop.city_pop", label: "City Pop", family: "pop" },
    { id: "jazz.lounge", label: "爵士", family: "chill" },
  ],
  timbres: [
    { id: "clear", label: "清亮" },
    { id: "breathy", label: "气声" },
  ],
  creativity: [
    { id: "pure", label: "纯正" },
    { id: "normal", label: "常规" },
    { id: "fusion", label: "融合" },
  ],
}

const base: AdvValue = {
  mood: [], vocal_gender: "", language: "", preset: "", vocal_timbre: "", creativity: "normal",
}

const setup = (value: Partial<AdvValue> = {}, styles: Styles | null = STYLES) => {
  const onChange = vi.fn()
  render(<AdvancedSettings value={{ ...base, ...value }} onChange={onChange} styles={styles} />)
  return onChange
}

describe("AdvancedSettings", () => {
  it("曲风按 family 分组,点击发送 id", () => {
    const onChange = setup()
    expect(screen.getByText("流行")).toBeTruthy()          // 分组名
    fireEvent.click(screen.getByText("City Pop"))
    expect(onChange).toHaveBeenCalledWith({ preset: "pop.city_pop" })
  })

  it("曲风「自动」清空 preset", () => {
    const onChange = setup({ preset: "jazz.lounge" })
    fireEvent.click(screen.getByRole("button", { name: "自动曲风" }))
    expect(onChange).toHaveBeenCalledWith({ preset: "" })
  })

  it("选中态按 id 判定", () => {
    setup({ preset: "jazz.lounge", vocal_timbre: "breathy", creativity: "fusion" })
    expect(screen.getByText("爵士").getAttribute("aria-pressed")).toBe("true")
    expect(screen.getByText("City Pop").getAttribute("aria-pressed")).toBe("false")
    expect(screen.getByText("气声").getAttribute("aria-pressed")).toBe("true")
    expect(screen.getByText("融合").getAttribute("aria-pressed")).toBe("true")
  })

  it("人声音色发送 id,「自动」清空", () => {
    const onChange = setup({ vocal_timbre: "clear" })
    fireEvent.click(screen.getByText("气声"))
    expect(onChange).toHaveBeenCalledWith({ vocal_timbre: "breathy" })
    fireEvent.click(screen.getByRole("button", { name: "自动音色" }))
    expect(onChange).toHaveBeenCalledWith({ vocal_timbre: "" })
  })

  it("创意度发送 id", () => {
    const onChange = setup()
    fireEvent.click(screen.getByText("纯正"))
    expect(onChange).toHaveBeenCalledWith({ creativity: "pure" })
  })

  it("情绪 chip 仍发送英文 tag", () => {
    const onChange = setup()
    fireEvent.click(screen.getByText("温柔"))
    expect(onChange).toHaveBeenCalledWith({ mood: ["gentle"] })
  })

  it("选项未加载时显示加载提示", () => {
    setup({}, null)
    expect(screen.getAllByText("加载中…").length).toBeGreaterThan(0)
  })
})
```

`web/test/GenerateForm.test.tsx`：把 `vi.mock("@/lib/api", …)` 改为

```tsx
vi.mock("@/lib/api", () => ({
  generate: vi.fn().mockResolvedValue({ job_id: "j1" }),
  getJob: vi.fn().mockResolvedValue({ status: "done", song: null }),
  getStyles: vi.fn().mockResolvedValue({
    genres: [{ id: "jazz.lounge", label: "爵士", family: "chill" }],
    timbres: [{ id: "breathy", label: "气声" }],
    creativity: [
      { id: "pure", label: "纯正" },
      { id: "normal", label: "常规" },
      { id: "fusion", label: "融合" },
    ],
  }),
}))
```

并在 describe 内追加：

```tsx
  it("曲风/音色/创意度随提交发送,不再发送 genre", async () => {
    vi.mocked(generate).mockClear()
    render(<GenerateForm />)
    fireEvent.click(await screen.findByText("爵士"))
    fireEvent.click(screen.getByText("气声"))
    fireEvent.click(screen.getByText("融合"))
    fireEvent.click(screen.getByText("✦ 生成我的歌曲"))
    await waitFor(() => expect(generate).toHaveBeenCalled())
    const o = vi.mocked(generate).mock.calls[0][0].overrides
    expect(o).toMatchObject({ preset: "jazz.lounge", vocal_timbre: "breathy", creativity: "fusion" })
    expect(o.genre).toBeUndefined()
  })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run test/AdvancedSettings.test.tsx test/GenerateForm.test.tsx`
Expected: FAIL（找不到「City Pop」等元素）

- [ ] **Step 3: Write minimal implementation**

`web/components/AdvancedSettings.tsx` 全文替换为：

```tsx
"use client"
import type { Creativity, StyleOption, Styles } from "@/lib/types"

// 显示中文、发送英文:中文 tag 混进 caption 会削弱 ACE-Step 的条件控制(后端对中文 tag 返回 422)。
export const MOODS = [
  { label: "温柔", tag: "gentle" },
  { label: "悲伤", tag: "sad" },
  { label: "治愈", tag: "healing" },
  { label: "浪漫", tag: "romantic" },
  { label: "欢乐", tag: "joyful" },
]

// 曲风分组名;后端新增 family 而这里没写时直接显示 family 原文
const FAMILY_LABEL: Record<string, string> = {
  pop: "流行",
  folk: "民谣",
  rock: "摇滚",
  rnb: "R&B",
  electronic: "电子",
  chill: "爵士 / 放松",
  cn: "中国风",
  hiphop: "说唱",
}

export interface AdvValue {
  mood: string[]
  vocal_gender: string
  language: string
  /** 曲风 id;空 = 自动(按「感觉」识别,识别不出随机) */
  preset: string
  /** 人声音色 id;空 = 按曲风自动挑 */
  vocal_timbre: string
  creativity: Creativity
}

function groupByFamily(genres: StyleOption[]): [string, StyleOption[]][] {
  const groups = new Map<string, StyleOption[]>()
  for (const g of genres) {
    const fam = g.family ?? ""
    groups.set(fam, [...(groups.get(fam) ?? []), g])
  }
  return [...groups.entries()]
}

export default function AdvancedSettings({
  value,
  onChange,
  styles,
}: {
  value: AdvValue
  onChange: (patch: Partial<AdvValue>) => void
  styles: Styles | null
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
  const row = { display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 12 } as const
  const label = (text: string) => (
    <p className="text-muted" style={{ fontSize: 12 }}>
      {text}
    </p>
  )
  const loading = (
    <span className="text-muted" style={{ fontSize: 12 }}>
      加载中…
    </span>
  )
  const toggle = (arr: string[], v: string) =>
    arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]
  const option = (o: StyleOption, on: boolean, onClick: () => void) => (
    <span key={o.id} role="button" aria-pressed={on} style={chip(on)} onClick={onClick}>
      {o.label}
    </span>
  )

  return (
    <div>
      {label("曲风")}
      <div style={{ marginBottom: 12 }}>
        <div style={row}>
          <span
            role="button"
            aria-label="自动曲风"
            aria-pressed={value.preset === ""}
            style={chip(value.preset === "")}
            onClick={() => onChange({ preset: "" })}
          >
            自动
          </span>
        </div>
        {styles
          ? groupByFamily(styles.genres).map(([fam, items]) => (
              <div key={fam} style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                <span className="text-muted" style={{ fontSize: 11, minWidth: 64 }}>
                  {FAMILY_LABEL[fam] ?? fam}
                </span>
                <div style={{ ...row, marginBottom: 6 }}>
                  {items.map((g) =>
                    option(g, value.preset === g.id, () => onChange({ preset: g.id })),
                  )}
                </div>
              </div>
            ))
          : loading}
      </div>

      {label("人声音色")}
      <div style={row}>
        <span
          role="button"
          aria-label="自动音色"
          aria-pressed={value.vocal_timbre === ""}
          style={chip(value.vocal_timbre === "")}
          onClick={() => onChange({ vocal_timbre: "" })}
        >
          自动
        </span>
        {styles
          ? styles.timbres.map((t) =>
              option(t, value.vocal_timbre === t.id, () => onChange({ vocal_timbre: t.id })),
            )
          : loading}
      </div>

      {label("创意度")}
      <div style={row}>
        {styles
          ? styles.creativity.map((c) =>
              option(c, value.creativity === c.id, () =>
                onChange({ creativity: c.id as Creativity }),
              ),
            )
          : loading}
      </div>

      {label("情绪")}
      <div style={row}>
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
      <div className="opts-row">
        <select
          value={value.vocal_gender}
          onChange={(e) => onChange({ vocal_gender: e.target.value })}
        >
          <option value="">人声(自动)</option>
          <option value="female">女声</option>
          <option value="male">男声</option>
        </select>
      </div>
    </div>
  )
}
```

`web/components/GenerateForm.tsx`：

1. import 增加 `import { useStyles } from "@/lib/styles"`；
2. 组件内加 `const styles = useStyles()`；
3. 初始 `adv` 改为：

```tsx
  const [adv, setAdv] = useState<AdvValue>({
    mood: [],
    vocal_gender: "",
    language: "",
    preset: "",
    vocal_timbre: "",
    creativity: "normal",
  })
```

4. 提交时 `overrides` 改为：

```tsx
      overrides: {
        preset: adv.preset,
        mood: adv.mood,
        vocal_gender: adv.vocal_gender,
        language: adv.language,
        vocal_timbre: adv.vocal_timbre,
        creativity: adv.creativity,
      },
```

5. `<AdvancedSettings … />` 加 `styles={styles}`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run && npx tsc --noEmit`
Expected: 全部通过；tsc 无输出。

- [ ] **Step 5: Commit**

```bash
git add web/components/AdvancedSettings.tsx web/components/GenerateForm.tsx web/test/AdvancedSettings.test.tsx web/test/GenerateForm.test.tsx
git commit -m "feat(web): 曲风分组网格、人声音色与创意度选择"
```

---

### Task 14: 歌曲卡片 — 风格摘要、新降级原因、「换一种」

**Files:**
- Modify: `web/components/SongCard.tsx`
- Modify: `web/app/library/page.tsx`
- Test: `web/test/SongCard.test.tsx`

**Interfaces:**
- Consumes: `useStyles`、`styleSummary`、`generate`。
- Produces: `SongCard` 新 prop `onRegenerate?: () => void`（提交成功后回调，库页据此重新开始轮询生成中任务）。「换一种」只在有 `style_draw` 的歌上显示，提交 `{lyrics, feeling, length: "auto", seed: null, instrumental, overrides: {preset: style_draw.preset_id, vocal_gender: spec.vocal.gender}}`。

- [ ] **Step 1: Write the failing test**

`web/test/SongCard.test.tsx`：

1. `vi.mock("@/lib/api", …)` 的对象里加：

```tsx
  // 用 vi.fn(impl) 而不是 mockResolvedValue:本文件 afterEach 会 restoreAllMocks,
  // 只有构造时传入的实现会被保留
  generate: vi.fn(async () => ({ job_id: "j9" })),
  getStyles: vi.fn(async () => ({
    genres: [{ id: "pop.city_pop", label: "City Pop", family: "pop" }],
    timbres: [{ id: "breathy", label: "气声" }],
    creativity: [],
  })),
```

2. 顶部 import 加 `generate`（从 `@/lib/api`）；
3. 追加：

```tsx
const styled = {
  ...song,
  lyrics: "[Verse]\n词",
  instrumental: 0,
  spec_json: JSON.stringify({
    vocal: { gender: "female" },
    style_draw: { preset_id: "pop.city_pop", vocal_timbre: "breathy",
                  vocal_gender: "female", bpm: 108, fusion_id: null },
  }),
} as Song

describe("SongCard 风格", () => {
  it("显示风格摘要", async () => {
    render(<SongCard song={styled} onPlay={vi.fn()} />)
    expect(await screen.findByText("City Pop · 气声女声 · 108 BPM")).toBeTruthy()
  })

  it("老歌不显示摘要和「换一种」", () => {
    render(<SongCard song={song} onPlay={vi.fn()} />)
    expect(screen.queryByText("换一种")).toBeNull()
  })

  it("「换一种」用同曲风同性别、新 seed 重新提交", async () => {
    const onRegenerate = vi.fn()
    render(<SongCard song={styled} onPlay={vi.fn()} onRegenerate={onRegenerate} />)
    fireEvent.click(screen.getByText("换一种"))
    await waitFor(() => expect(onRegenerate).toHaveBeenCalled())
    const input = vi.mocked(generate).mock.calls.at(-1)![0]
    expect(input).toMatchObject({
      lyrics: "[Verse]\n词", feeling: song.feeling, seed: null, length: "auto",
      overrides: { preset: "pop.city_pop", vocal_gender: "female" },
    })
  })

  it("新降级原因有中文说明", () => {
    const s = { ...song, llm_status: JSON.stringify([
      { stage: "歌曲规划", ok: false, reason: "missing_timbre" }]) } as Song
    render(<SongCard song={s} onPlay={vi.fn()} />)
    expect(screen.getByText("降级").getAttribute("title")).toContain("缺少人声音色")
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run test/SongCard.test.tsx`
Expected: FAIL（找不到摘要文本与「换一种」）

- [ ] **Step 3: Write minimal implementation**

`web/components/SongCard.tsx`：

1. import：`generate` 加入 `@/lib/api` 的导入列表；新增 `import { styleSummary, useStyles } from "@/lib/styles"`；
2. `REASON_TEXT` 追加：

```tsx
  missing_genre: "模型输出缺少曲风词",
  missing_timbre: "模型输出缺少人声音色",
  conflict: "模型输出含冲突的风格词",
  unknown_genre: "未能识别曲风，已随机选择",
```

3. props 增加：

```tsx
  /** 「换一种」提交成功后回调;库页借此重新开始轮询生成中的任务 */
  onRegenerate?: () => void
```

4. 组件内 state 区追加：

```tsx
  const styles = useStyles()
  const summary = styleSummary(song.spec_json, styles)
  const [regenNote, setRegenNote] = useState("")

  async function handleRegenerate() {
    if (regenNote) return
    try {
      const spec = JSON.parse(song.spec_json)
      // 同曲风、同性别、新 seed:换一组乐器/音色/质感,而不是换成别的曲风
      await generate({
        lyrics: song.lyrics,
        title: "",
        feeling: song.feeling,
        length: "auto",
        seed: null,
        instrumental: song.instrumental === 1,
        overrides: {
          preset: spec.style_draw.preset_id,
          vocal_gender: spec.vocal?.gender || "",
        },
      })
      setRegenNote("已提交")
      onRegenerate?.()
    } catch {
      setRegenNote("提交失败")
    }
    setTimeout(() => setRegenNote(""), 2000)
  }
```

5. 在显示 `{song.feeling}` 的 `<div className="text-muted" …>` 之后插入：

```tsx
        {summary && (
          <div
            style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 7 }}
          >
            <span className="text-muted" style={{ fontSize: 10.5 }}>
              {summary}
            </span>
            <button
              onClick={handleRegenerate}
              disabled={!!regenNote}
              title="同曲风换一组乐器与音色,重新生成"
              style={{
                border: "1px solid var(--line)",
                background: "rgba(255,255,255,.55)",
                color: "var(--brand)",
                borderRadius: 6,
                fontSize: 10.5,
                padding: "1px 6px",
                cursor: regenNote ? "default" : "pointer",
                flex: "0 0 auto",
              }}
            >
              {regenNote || "换一种"}
            </button>
          </div>
        )}
```

`web/app/library/page.tsx`：

1. 加 state：`const [pendingNonce, setPendingNonce] = useState(0)`；
2. 轮询 `useEffect` 的依赖数组改为 `[showPending, loadSongs, pendingNonce]`（轮询在没有任务时会停，新提交的任务要靠它重新启动）；
3. `<SongCard …>` 加 `onRegenerate={() => setPendingNonce((n) => n + 1)}`。

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run && npx tsc --noEmit`
Expected: 全部通过；tsc 无输出。

- [ ] **Step 5: Commit**

```bash
git add web/components/SongCard.tsx web/app/library/page.tsx web/test/SongCard.test.tsx
git commit -m "feat(web): 歌曲卡片显示风格摘要,新增「换一种」与新降级原因说明"
```

---

### Task 15: 评测网格脚本与改后结果

**Files:**
- Create: `scripts/style_grid.py`
- Modify: `docs/superpowers/evals/style-grid.md`

- [ ] **Step 1: 写脚本**

```python
# scripts/style_grid.py
"""风格网格评测:同一段歌词 × 14 个曲风 × 固定 seed,只跑 识别/采样/planner(不出歌)。

用法(项目根目录,需 .env 里的 LLM key):
  set -a; . ./.env; set +a
  .venv/bin/python scripts/style_grid.py [--seed 1001] [--creativity normal]
"""
import argparse
import itertools
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import config  # noqa: E402
from src import planner  # noqa: E402
from src.presets import UI_GENRES, get_preset  # noqa: E402
from src.style_sampler import sample_style  # noqa: E402

STOP = {"a", "an", "the", "and", "with", "of", "in", "on", "over", "by", "its", "is", "to",
        "that", "as", "into", "for"}


def tokens(caption: str) -> set[str]:
    return {t for t in re.findall(r"[a-z][a-z&'-]+", caption.lower()) if t not in STOP}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1001)
    ap.add_argument("--creativity", default="normal")
    args = ap.parse_args()

    opts = {"provider": config.LLM_PROVIDER}
    rows, caps, hits, degraded = [], [], 0, 0
    for pid in UI_GENRES:
        preset = get_preset(pid)
        draw = sample_style(preset, seed=args.seed, creativity=args.creativity)
        events: list[dict] = []
        spec = planner.plan_song("", preset=preset, draw=draw, llm_options=opts,
                                 status_events=events)
        hit = any(k in spec.caption.lower() for k in preset.caption_keywords)
        hits += hit
        degraded += any(not e["ok"] for e in events)
        caps.append(spec.caption)
        rows.append(f"| {preset.label} | {draw.vocal_timbre} | {', '.join(draw.instruments)} "
                    f"| {'✓' if hit else '✗'} | {spec.caption[:120]} |")

    jac = [len(tokens(a) & tokens(b)) / len(tokens(a) | tokens(b))
           for a, b in itertools.combinations(caps, 2)]
    print("| 曲风 | 音色 | 乐器 | 命中 | caption(前 120 字) |\n|---|---|---|---|---|")
    print("\n".join(rows))
    print(f"\n曲风命中率: {hits}/{len(UI_GENRES)}")
    print(f"降级率: {degraded}/{len(UI_GENRES)}")
    print(f"两两 Jaccard 均值: {statistics.mean(jac):.3f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑评测**

```bash
set -a; . ./.env; set +a
.venv/bin/python scripts/style_grid.py --seed 1001
.venv/bin/python scripts/style_grid.py --seed 1002
```

Expected: 命中率 14/14；Jaccard 均值 < 0.25 且明显低于 Task 0 基线。若命中率不足或降级率高，记下具体 caption 回头改对应曲风数据（不改校验规则）。

- [ ] **Step 3: 填写评测文档**

在 `docs/superpowers/evals/style-grid.md` 的「改动后」下贴两次输出（表格 + 三个指标），并加一行与基线的对比结论。盲听一栏留待出歌后填写。

- [ ] **Step 4: Commit**

```bash
git add scripts/style_grid.py docs/superpowers/evals/style-grid.md
git commit -m "docs(evals): 风格网格评测脚本与改后结果"
```

---

### Task 16: 全量回归、真实出歌验收与上线

**Files:** 无代码改动（发现问题则回到对应任务修复）。

- [ ] **Step 1: 全量测试**

```bash
.venv/bin/python -m pytest tests/ -q
cd web && npx vitest run && npx tsc --noEmit && cd ..
```

Expected: 全部通过。

- [ ] **Step 2: 本机真实出歌（至少 3 首）**

确认后台空闲（`ps -o rss= -p $(pgrep -f "uvicorn server.app")` 很小，说明模型未加载），然后重启后端让新代码生效：

```bash
launchctl kickstart -k gui/$(id -u)/com.zemusic.backend
```

用 `curl` 提交 3 首同一段歌词、不同曲风（例如 `pop.city_pop` + `breathy`、`rock.band` + `raspy`、`cn.guofeng` + `fusion`），参考 `docs/superpowers/evals/hiphop-ab.md` 的提交方式，`overrides` 换成新字段。检查：
  - `backend.log` 里 DiT 收到的 caption 含所选曲风与音色词；
  - 库里 `songs.seed` 非空、`spec_json` 含 `style_draw`；
  - 前端卡片显示风格摘要，「换一种」能提交并出现在「生成中」。

把 3 首的盲听结果填进 `style-grid.md`。

- [ ] **Step 3: 上线前端**

后端新接口兼容旧前端（旧前端只发 `genre` / `preset`，仍被接受），所以顺序是先后端（Step 2 已重启），再推前端：

```bash
git push origin feat/song-generator-v0.1
```

推送即触发 Vercel 构建。构建完成后在线上页面确认曲风网格能加载（依赖 `GET /api/styles` 经 Tailscale Funnel 可达）。

- [ ] **Step 4: Commit（如有评测文档更新）**

```bash
git add docs/superpowers/evals/style-grid.md
git commit -m "docs(evals): 多曲风真实出歌验收记录"
git push origin feat/song-generator-v0.1
```
