# AI 成曲 Demo V0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让不懂音乐的用户只写歌词 + 一句话感觉，就生成一首完整中文歌曲。

**Architecture:** `歌词 + 一句话感觉 → planner(LLM API 产出 SongSpec) → lyrics(LLM 结构化歌词) → song_gen(ACE-Step 1.5) → 完整歌曲`。纯逻辑（Spec 校验、planner/lyrics、参数映射、pipeline 编排）用 mock LLM 做 TDD，在任意机器可跑；真实模型调用（ACE-Step）在 Colab 冒烟测试。LLM 调用封装成单一接口，可切换实现。

**Tech Stack:** Python 3.10+、pydantic v2（SongSpec 校验）、anthropic SDK（文本 LLM）、ACE-Step 1.5（成曲）、Gradio（UI）、pytest（测试）、Colab（部署）。

## Global Constraints

- Python 3.10+。
- LLM 用文本 API（方案 A），默认模型 `claude-haiku-4-5-20251001`，key 从环境变量 `ANTHROPIC_API_KEY` 读；模型名从 `LLM_MODEL` 读，缺省用默认。
- **专业参数不暴露给普通用户**：BPM/Key/Seed/Pitch/Steps/CFG/时长秒数 一律放"高级设置"或内部映射；主界面只有 歌词、感觉、生成。
- 中文优先：SongSpec `language` 默认 `"zh"`。
- 所有 LLM 调用只经 `src/llm.py` 的 `complete()`，其它模块不得直接 import anthropic。
- 重模型（ACE-Step 等）在模块函数内部**惰性 import**，保证纯逻辑模块在无 GPU 依赖的机器上可导入、可测试。
- V0.1 范围内**不实现** Demucs / Seed-VC / repaint（那是 V0.2/V0.3）。
- 每个纯逻辑任务遵循 TDD：先写失败测试 → 跑失败 → 最小实现 → 跑通过 → 提交。

---

## File Structure

```
music/
├── app.py                    # Task 8  Gradio 极简 UI
├── requirements.txt          # Task 1  Colab 全量依赖（pin）
├── requirements-dev.txt      # Task 1  本地测试轻量依赖
├── .gitignore                # Task 1
├── config.py                 # Task 1  设备/路径/LLM 配置
├── colab.ipynb               # Task 9  一键部署
├── src/
│   ├── __init__.py           # Task 1
│   ├── spec.py               # Task 2  SongSpec 模型 + 安全默认 + 解析
│   ├── llm.py                # Task 3  LLM 单一接口 complete()
│   ├── planner.py            # Task 4  自然语言 → SongSpec
│   ├── lyrics.py             # Task 5  自由歌词 → 结构化歌词
│   ├── song_gen.py           # Task 6  ACE-Step 参数映射(纯) + 成曲(惰性)
│   └── pipeline.py           # Task 7  编排 make_song
├── assets/                   # 预留（V0.3 参考声）
├── outputs/                  # 产物落盘（.gitignore）
└── tests/
    ├── __init__.py           # Task 1
    ├── test_spec.py          # Task 2
    ├── test_llm.py           # Task 3
    ├── test_planner.py       # Task 4
    ├── test_lyrics.py        # Task 5
    ├── test_song_gen.py      # Task 6
    └── test_pipeline.py      # Task 7
```

---

## Task 1: 项目脚手架与配置

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `config.py`, `src/__init__.py`, `tests/__init__.py`, `outputs/.gitkeep`, `assets/.gitkeep`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `config.get_device() -> str`（返回 `"cuda"|"mps"|"cpu"` 之一）
  - `config.LLM_MODEL: str`
  - `config.OUTPUTS_DIR: str`、`config.ASSETS_DIR: str`、`config.BASE_DIR: str`
  - `config.ensure_dirs() -> None`（创建 outputs/assets）

- [ ] **Step 1: 写失败测试**

`tests/test_config.py`：
```python
import os
import config


def test_get_device_returns_valid_value():
    assert config.get_device() in {"cuda", "mps", "cpu"}


def test_llm_model_has_default():
    assert isinstance(config.LLM_MODEL, str) and config.LLM_MODEL


def test_ensure_dirs_creates_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUTS_DIR", str(tmp_path / "out"))
    monkeypatch.setattr(config, "ASSETS_DIR", str(tmp_path / "assets"))
    config.ensure_dirs()
    assert os.path.isdir(config.OUTPUTS_DIR)
    assert os.path.isdir(config.ASSETS_DIR)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pip install -r requirements-dev.txt && pytest tests/test_config.py -v`
Expected: FAIL（`ModuleNotFoundError: config` 或属性缺失）

- [ ] **Step 3: 写最小实现**

`requirements-dev.txt`：
```
pytest==8.3.4
pydantic==2.10.4
anthropic==0.42.0
gradio==5.9.1
```

`requirements.txt`（Colab 全量；ACE-Step 版本以其 README 为准，安装步骤在 colab.ipynb）：
```
pytest==8.3.4
pydantic==2.10.4
anthropic==0.42.0
gradio==5.9.1
torch
torchaudio
# ACE-Step 1.5：按官方 README 从源码/包安装，见 colab.ipynb
```

`.gitignore`：
```
__pycache__/
*.pyc
outputs/*
!outputs/.gitkeep
.venv/
.env
*.wav
```

`config.py`：
```python
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

LLM_MODEL = os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")


def get_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def ensure_dirs() -> None:
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)
```

创建空文件 `src/__init__.py`、`tests/__init__.py`、`outputs/.gitkeep`、`assets/.gitkeep`。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_config.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add requirements.txt requirements-dev.txt .gitignore config.py src/__init__.py tests/__init__.py tests/test_config.py outputs/.gitkeep assets/.gitkeep
git commit -m "chore: 脚手架与配置(config, 依赖, gitignore)"
```

---

## Task 2: SongSpec 数据契约

**Files:**
- Create: `src/spec.py`
- Test: `tests/test_spec.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `class VocalSpec(BaseModel)`：`gender: str = "female"`、`style: str = "soft"`
  - `class SongSpec(BaseModel)`：`language: str = "zh"`、`vocal: VocalSpec`、`genre: list[str]`、`mood: list[str]`、`instrument: list[str]`、`bpm: int`（40–200）、`structure: list[str]`
  - `SAFE_DEFAULT_SPEC: dict`（合法的中性默认）
  - `def parse_spec(data: dict) -> SongSpec`（校验并规整；非法则抛 `ValueError`）
  - `def safe_spec() -> SongSpec`（返回 `SongSpec(**SAFE_DEFAULT_SPEC)`）

- [ ] **Step 1: 写失败测试**

`tests/test_spec.py`：
```python
import pytest
from src.spec import SongSpec, parse_spec, safe_spec, SAFE_DEFAULT_SPEC


def test_safe_default_is_valid():
    spec = safe_spec()
    assert spec.language == "zh"
    assert 40 <= spec.bpm <= 200
    assert spec.structure  # 非空


def test_parse_valid_dict():
    data = {
        "language": "zh",
        "vocal": {"gender": "male", "style": "powerful"},
        "genre": ["rock"],
        "mood": ["angry"],
        "instrument": ["electric guitar"],
        "bpm": 140,
        "structure": ["Intro", "Verse", "Chorus"],
    }
    spec = parse_spec(data)
    assert spec.vocal.gender == "male"
    assert spec.bpm == 140


def test_parse_out_of_range_bpm_raises():
    data = dict(SAFE_DEFAULT_SPEC)
    data["bpm"] = 9999
    with pytest.raises(ValueError):
        parse_spec(data)


def test_parse_missing_field_uses_model_default():
    # 缺 vocal 时用默认 VocalSpec
    data = {k: v for k, v in SAFE_DEFAULT_SPEC.items() if k != "vocal"}
    spec = parse_spec(data)
    assert spec.vocal.gender == "female"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_spec.py -v`
Expected: FAIL（`ModuleNotFoundError: src.spec`）

- [ ] **Step 3: 写最小实现**

`src/spec.py`：
```python
from pydantic import BaseModel, Field, ValidationError


class VocalSpec(BaseModel):
    gender: str = "female"
    style: str = "soft"


class SongSpec(BaseModel):
    language: str = "zh"
    vocal: VocalSpec = Field(default_factory=VocalSpec)
    genre: list[str] = Field(default_factory=lambda: ["mandopop"])
    mood: list[str] = Field(default_factory=lambda: ["warm"])
    instrument: list[str] = Field(default_factory=lambda: ["piano"])
    bpm: int = Field(default=90, ge=40, le=200)
    structure: list[str] = Field(
        default_factory=lambda: ["Intro", "Verse", "Chorus", "Verse", "Chorus", "Outro"]
    )


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
    return SongSpec(**SAFE_DEFAULT_SPEC)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_spec.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add src/spec.py tests/test_spec.py
git commit -m "feat: SongSpec 数据契约与安全默认"
```

---

## Task 3: LLM 单一接口

**Files:**
- Create: `src/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `config.LLM_MODEL`
- Produces: `def complete(prompt: str, system: str = "") -> str`（调用文本 LLM，返回纯文本）

- [ ] **Step 1: 写失败测试**

`tests/test_llm.py`（不打真实网络；验证接口存在、真实调用用 skipif 冒烟）：
```python
import os
import pytest
from src import llm


def test_complete_is_callable():
    assert callable(llm.complete)


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"), reason="需要真实 API key"
)
def test_complete_smoke():
    out = llm.complete("只回复一个字：好", system="你是测试助手")
    assert isinstance(out, str) and out.strip()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL（`ModuleNotFoundError: src.llm`）

- [ ] **Step 3: 写最小实现**

`src/llm.py`：
```python
import os
from config import LLM_MODEL


def complete(prompt: str, system: str = "") -> str:
    """调用文本 LLM，返回纯文本。V0.1 唯一的 LLM 出入口。"""
    from anthropic import Anthropic

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=LLM_MODEL,
        max_tokens=2048,
        system=system or "You are a helpful assistant.",
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(
        block.text for block in msg.content if getattr(block, "type", None) == "text"
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_llm.py -v`
Expected: PASS（1 passed, 1 skipped 若无 key）

- [ ] **Step 5: 提交**

```bash
git add src/llm.py tests/test_llm.py
git commit -m "feat: LLM 单一接口 complete()"
```

---

## Task 4: Planner（自然语言 → SongSpec）

**Files:**
- Create: `src/planner.py`
- Test: `tests/test_planner.py`

**Interfaces:**
- Consumes: `src.llm.complete`、`src.spec.parse_spec`、`src.spec.safe_spec`、`src.spec.SongSpec`
- Produces: `def plan_song(style_desc: str, lyrics_hint: str = "") -> SongSpec`

行为：构造提示词要求 LLM 输出 JSON SongSpec → 提取 JSON → `parse_spec`；任何异常（网络、非 JSON、校验失败）都回退 `safe_spec()`，保证链路不中断。

- [ ] **Step 1: 写失败测试**

`tests/test_planner.py`（monkeypatch `llm.complete`，不打网络）：
```python
import json
from src import planner
from src.spec import SongSpec, SAFE_DEFAULT_SPEC


def test_plan_song_parses_llm_json(monkeypatch):
    fake = {
        "language": "zh",
        "vocal": {"gender": "female", "style": "soft"},
        "genre": ["r&b"],
        "mood": ["nostalgic"],
        "instrument": ["piano"],
        "bpm": 82,
        "structure": ["Intro", "Verse", "Chorus"],
    }
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: json.dumps(fake))
    spec = planner.plan_song("女声，R&B，深夜，温柔")
    assert isinstance(spec, SongSpec)
    assert spec.bpm == 82
    assert "r&b" in spec.genre


def test_plan_song_json_in_code_fence(monkeypatch):
    fake = json.dumps(SAFE_DEFAULT_SPEC)
    monkeypatch.setattr(
        planner.llm, "complete", lambda *a, **k: f"```json\n{fake}\n```"
    )
    spec = planner.plan_song("随便")
    assert spec.language == "zh"


def test_plan_song_falls_back_on_garbage(monkeypatch):
    monkeypatch.setattr(planner.llm, "complete", lambda *a, **k: "抱歉我不会")
    spec = planner.plan_song("女声")
    assert spec.bpm == SAFE_DEFAULT_SPEC["bpm"]  # 回退默认


def test_plan_song_falls_back_on_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(planner.llm, "complete", boom)
    spec = planner.plan_song("女声")
    assert spec.language == "zh"  # 未抛异常，回退成功
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_planner.py -v`
Expected: FAIL（`ModuleNotFoundError: src.planner`）

- [ ] **Step 3: 写最小实现**

`src/planner.py`：
```python
import json
import re
from src import llm
from src.spec import SongSpec, parse_spec, safe_spec

_SYSTEM = "你是音乐制作人。根据用户对歌曲感觉的描述，只输出一个 JSON 对象，不要多余文字。"

_TEMPLATE = """用户想要的感觉：{style}
{hint}
请输出 JSON，字段：
language(如 zh), vocal{{gender, style}}, genre(数组), mood(数组),
instrument(数组), bpm(40-200 整数), structure(数组, 如 Intro/Verse/Pre-Chorus/Chorus/Bridge/Outro)。
只输出 JSON。"""


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no json object in llm output")
    return json.loads(m.group(0))


def plan_song(style_desc: str, lyrics_hint: str = "") -> SongSpec:
    hint = f"歌词片段参考：{lyrics_hint}" if lyrics_hint else ""
    prompt = _TEMPLATE.format(style=style_desc, hint=hint)
    try:
        raw = llm.complete(prompt, system=_SYSTEM)
        return parse_spec(_extract_json(raw))
    except Exception:
        return safe_spec()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_planner.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add src/planner.py tests/test_planner.py
git commit -m "feat: planner 自然语言->SongSpec, 失败回退默认"
```

---

## Task 5: Lyrics（自由歌词 → 结构化）

**Files:**
- Create: `src/lyrics.py`
- Test: `tests/test_lyrics.py`

**Interfaces:**
- Consumes: `src.llm.complete`、`src.spec.SongSpec`
- Produces: `def structure_lyrics(raw_lyrics: str, spec: SongSpec) -> str`（返回带 `[Verse]`/`[Chorus]` 等标签的字符串）

行为：用 spec.structure 引导 LLM 给自由歌词打段落标签；LLM 失败时回退——把全部歌词包进 `[Verse]` 与 `[Chorus]`，保证下游拿到合法结构。

- [ ] **Step 1: 写失败测试**

`tests/test_lyrics.py`：
```python
from src import lyrics
from src.spec import safe_spec


def test_structure_lyrics_uses_llm(monkeypatch):
    monkeypatch.setattr(
        lyrics.llm, "complete",
        lambda *a, **k: "[Verse]\n我曾走过那条街\n[Chorus]\n后来啊",
    )
    out = lyrics.structure_lyrics("我曾走过那条街\n后来啊", safe_spec())
    assert "[Verse]" in out and "[Chorus]" in out


def test_structure_lyrics_fallback_on_exception(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(lyrics.llm, "complete", boom)
    out = lyrics.structure_lyrics("第一句\n第二句", safe_spec())
    assert "[Verse]" in out
    assert "第一句" in out  # 原歌词保留


def test_structure_lyrics_fallback_on_empty(monkeypatch):
    monkeypatch.setattr(lyrics.llm, "complete", lambda *a, **k: "   ")
    out = lyrics.structure_lyrics("只有一句", safe_spec())
    assert "[Verse]" in out and "只有一句" in out
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_lyrics.py -v`
Expected: FAIL（`ModuleNotFoundError: src.lyrics`）

- [ ] **Step 3: 写最小实现**

`src/lyrics.py`：
```python
from src import llm
from src.spec import SongSpec

_SYSTEM = "你是作词编辑。把用户歌词按给定歌曲结构分段，用 [Verse]/[Chorus] 等标签标注，保留原词，不要新增大量歌词。"


def _fallback(raw_lyrics: str) -> str:
    body = raw_lyrics.strip() or "……"
    return f"[Verse]\n{body}\n\n[Chorus]\n{body}"


def structure_lyrics(raw_lyrics: str, spec: SongSpec) -> str:
    structure = " / ".join(spec.structure)
    prompt = (
        f"歌曲结构：{structure}\n"
        f"请按此结构给下面的歌词分段并加标签：\n{raw_lyrics}"
    )
    try:
        out = llm.complete(prompt, system=_SYSTEM)
        if out and "[" in out:
            return out.strip()
        return _fallback(raw_lyrics)
    except Exception:
        return _fallback(raw_lyrics)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_lyrics.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add src/lyrics.py tests/test_lyrics.py
git commit -m "feat: lyrics 自由歌词->结构化, 失败回退"
```

---

## Task 6: Song 生成（ACE-Step 参数映射 + 成曲）

**Files:**
- Create: `src/song_gen.py`
- Test: `tests/test_song_gen.py`

**Interfaces:**
- Consumes: `src.spec.SongSpec`、`config.get_device`
- Produces:
  - `def build_acestep_params(spec: SongSpec, length: str = "full", seed: int | None = None) -> dict`（**纯函数**，可单测；含 `prompt`、`duration`、`seed`、`bpm`）
  - `def generate_song(structured_lyrics: str, spec: SongSpec, *, length: str = "full", seed: int | None = None, out_path: str) -> str`（惰性 import ACE-Step，Colab 冒烟；返回 `out_path`）

length 映射：`"short" -> 45`、`"full" -> 210`。prompt 由 genre+mood+instrument+vocal 拼成逗号分隔标签串。

- [ ] **Step 1: 写失败测试**（只测纯函数 `build_acestep_params`）

`tests/test_song_gen.py`：
```python
from src.song_gen import build_acestep_params
from src.spec import safe_spec


def test_length_short_maps_to_short_duration():
    p = build_acestep_params(safe_spec(), length="short")
    assert p["duration"] == 45


def test_length_full_maps_to_full_duration():
    p = build_acestep_params(safe_spec(), length="full")
    assert p["duration"] == 210


def test_prompt_contains_genre_and_instrument():
    spec = safe_spec()  # genre=[mandopop], instrument=[piano, soft drums]
    p = build_acestep_params(spec)
    assert "mandopop" in p["prompt"]
    assert "piano" in p["prompt"]


def test_seed_passthrough():
    p = build_acestep_params(safe_spec(), seed=123)
    assert p["seed"] == 123
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_song_gen.py -v`
Expected: FAIL（`ModuleNotFoundError: src.song_gen`）

- [ ] **Step 3: 写最小实现**

`src/song_gen.py`：
```python
from src.spec import SongSpec

_LENGTH_MAP = {"short": 45, "full": 210}


def build_acestep_params(spec: SongSpec, length: str = "full", seed: int | None = None) -> dict:
    tags = [*spec.genre, *spec.mood, *spec.instrument,
            f"{spec.vocal.gender} vocal", spec.vocal.style]
    return {
        "prompt": ", ".join(t for t in tags if t),
        "duration": _LENGTH_MAP.get(length, _LENGTH_MAP["full"]),
        "bpm": spec.bpm,
        "language": spec.language,
        "seed": seed,
    }


def generate_song(structured_lyrics: str, spec: SongSpec, *,
                  length: str = "full", seed: int | None = None, out_path: str) -> str:
    """惰性 import ACE-Step 1.5 并生成歌曲，保存到 out_path 后返回。
    ⚠ 集成点：以 Colab 上 `pip show` 出来的 ACE-Step 1.5 实际 API 为准，
    在 Step 4(Colab 冒烟) 时对照官方 README 调整下面的调用签名。
    """
    from config import get_device
    params = build_acestep_params(spec, length=length, seed=seed)

    # 下面为对接占位：按 ACE-Step 1.5 README 的推理入口替换。
    from acestep.pipeline_ace_step import ACEStepPipeline  # 名称以官方为准
    pipe = ACEStepPipeline(device=get_device())
    pipe(
        prompt=params["prompt"],
        lyrics=structured_lyrics,
        audio_duration=params["duration"],
        infer_step=27,
        manual_seeds=str(params["seed"]) if params["seed"] is not None else None,
        save_path=out_path,
    )
    return out_path
```

- [ ] **Step 4: 跑测试确认通过 + Colab 冒烟**

Run（本机，纯函数）: `pytest tests/test_song_gen.py -v` → Expected: PASS（4 passed）
Colab 冒烟（GPU）: 装好 ACE-Step 1.5 后，对照官方 README 校正 `generate_song` 里的 import 路径与调用参数名，跑：
```python
from src.song_gen import generate_song
from src.spec import safe_spec
p = generate_song("[Verse]\n测试一句\n[Chorus]\n测试副歌",
                  safe_spec(), length="short", out_path="outputs/smoke.wav")
import os; assert os.path.getsize(p) > 0
```
Expected: 生成非空 `outputs/smoke.wav`，可试听。

- [ ] **Step 5: 提交**

```bash
git add src/song_gen.py tests/test_song_gen.py
git commit -m "feat: song_gen 参数映射(纯)+ACE-Step 成曲(惰性)"
```

---

## Task 7: Pipeline 编排

**Files:**
- Create: `src/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `src.planner.plan_song`、`src.lyrics.structure_lyrics`、`src.song_gen.generate_song`、`config.ensure_dirs`、`config.OUTPUTS_DIR`
- Produces: `def make_song(raw_lyrics: str, style_desc: str, *, length: str = "full", seed: int | None = None, work_dir: str | None = None) -> dict`
  返回 `{"spec": SongSpec, "structured_lyrics": str, "song": str}`（`song` 为 wav 路径）

- [ ] **Step 1: 写失败测试**（monkeypatch song_gen，避免真实模型；planner/lyrics 用 mock llm）

`tests/test_pipeline.py`：
```python
import json
from src import pipeline
from src.spec import SAFE_DEFAULT_SPEC, SongSpec


def test_make_song_orchestrates(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pipeline.planner.llm, "complete", lambda *a, **k: json.dumps(SAFE_DEFAULT_SPEC)
    )
    monkeypatch.setattr(
        pipeline.lyrics.llm, "complete", lambda *a, **k: "[Verse]\nx\n[Chorus]\ny"
    )

    captured = {}
    def fake_gen(structured_lyrics, spec, *, length, seed, out_path):
        captured["lyrics"] = structured_lyrics
        captured["length"] = length
        with open(out_path, "wb") as f:
            f.write(b"RIFF")
        return out_path
    monkeypatch.setattr(pipeline.song_gen, "generate_song", fake_gen)

    result = pipeline.make_song(
        "我的歌词", "女声 R&B", length="short", work_dir=str(tmp_path)
    )
    assert isinstance(result["spec"], SongSpec)
    assert "[Verse]" in result["structured_lyrics"]
    assert result["song"].endswith(".wav")
    assert captured["length"] == "short"
    assert "[Verse]" in captured["lyrics"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL（`ModuleNotFoundError: src.pipeline`）

- [ ] **Step 3: 写最小实现**

`src/pipeline.py`：
```python
import os
import config
from src import planner, lyrics, song_gen


def make_song(raw_lyrics: str, style_desc: str, *,
              length: str = "full", seed: int | None = None,
              work_dir: str | None = None) -> dict:
    out_dir = work_dir or config.OUTPUTS_DIR
    os.makedirs(out_dir, exist_ok=True)

    spec = planner.plan_song(style_desc, lyrics_hint=raw_lyrics[:80])
    structured = lyrics.structure_lyrics(raw_lyrics, spec)
    song_path = os.path.join(out_dir, "song.wav")
    song_gen.generate_song(
        structured, spec, length=length, seed=seed, out_path=song_path
    )
    return {"spec": spec, "structured_lyrics": structured, "song": song_path}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS（1 passed）；再跑全量 `pytest -v` 确认前序任务无回归。

- [ ] **Step 5: 提交**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline make_song 编排全链路"
```

---

## Task 8: Gradio 极简 UI

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: `src.pipeline.make_song`、`config.ensure_dirs`
- Produces: 可运行的 Gradio 应用（`python app.py` 启动；`demo` 对象供 colab 用 `share=True`）

无自动化单测（UI），用手动验收。

- [ ] **Step 1: 写实现**

`app.py`：
```python
import gradio as gr
import config
from src.pipeline import make_song

config.ensure_dirs()


def on_generate(lyrics_text, feeling, length_label, seed):
    length = "short" if length_label == "短版 Demo" else "full"
    seed_val = int(seed) if str(seed).strip() else None
    result = make_song(lyrics_text, feeling, length=length, seed=seed_val)
    return result["song"], result["structured_lyrics"]


with gr.Blocks(title="把歌词变成一首歌") as demo:
    gr.Markdown("## 🎵 把歌词变成一首歌")
    lyrics_in = gr.Textbox(label="歌词", lines=8, placeholder="我曾走过那条街……")
    feeling_in = gr.Textbox(
        label="你想要什么感觉？", placeholder="女声，R&B，深夜，温柔"
    )
    with gr.Accordion("高级设置", open=False):
        length_in = gr.Radio(
            ["短版 Demo", "完整歌曲"], value="完整歌曲", label="歌曲长度"
        )
        seed_in = gr.Textbox(label="Seed（留空随机）", value="")
    btn = gr.Button("帮我做成一首歌", variant="primary")
    audio_out = gr.Audio(label="成品", type="filepath")
    struct_out = gr.Textbox(label="结构化歌词", lines=8)
    gr.Markdown("_音色转换等功能见后续版本。克隆他人声音请确保已获授权。_")

    btn.click(
        on_generate,
        [lyrics_in, feeling_in, length_in, seed_in],
        [audio_out, struct_out],
    )

if __name__ == "__main__":
    demo.launch()
```

- [ ] **Step 2: 本机导入自检**

Run: `python -c "import app; print('ok')"`
Expected: 打印 `ok`（无语法/导入错误；不真正启动模型）。

- [ ] **Step 3: 提交**

```bash
git add app.py
git commit -m "feat: Gradio 极简 UI (歌词+感觉+生成, 参数折叠)"
```

- [ ] **Step 4: 手动验收（Colab，见 Task 9 之后）**

在 Colab GPU 上填真实中文歌词 + 一句话感觉，点生成，试听成品并下载。

---

## Task 9: Colab 一键部署 Notebook

**Files:**
- Create: `colab.ipynb`

**Interfaces:**
- Consumes: `requirements.txt`、ACE-Step 1.5 官方安装方式、`app.py`
- Produces: 可在 Colab 顺序执行、最终 `demo.launch(share=True)` 出公网链接的 notebook

无自动化单测，人工在 Colab 跑通即验收。

- [ ] **Step 1: 写 notebook（cell 顺序）**

1. 克隆本仓库、`cd music`
2. `pip install -r requirements.txt`
3. 按 ACE-Step 1.5 官方 README 安装其权重/包（**首跑实测确认 VRAM，若 OOM 用短版/减 infer_step**）
4. `import os; os.environ["ANTHROPIC_API_KEY"]="..."`（用 Colab secrets 填入）
5. 冒烟：跑 Task 6 Step 4 的 `generate_song` 短版，确认出非空 wav
6. 启动：
   ```python
   import app
   app.demo.launch(share=True)
   ```

- [ ] **Step 2: Colab 跑通验收**

在 Colab 依次执行所有 cell → 拿到 share 链接 → 完成 Task 8 手动验收（真实歌词出歌、试听、下载）。

- [ ] **Step 3: 提交**

```bash
git add colab.ipynb
git commit -m "feat: Colab 一键部署 notebook"
```

---

## Self-Review

**Spec coverage：**
- 目标"歌词+一句话→出歌" → Task 4/5/6/7/8 ✓
- Song Planner（自然语言→SongSpec） → Task 4 ✓
- 歌词结构化 → Task 5 ✓
- ACE-Step 1.5 成曲 + length 映射不暴露秒数 → Task 6 ✓
- 极简 UI + 专业参数折叠 → Task 8 ✓
- LLM 用 API(方案A)、单一接口可切换 → Task 3 + Global Constraints ✓
- Colab 部署、首跑实测 VRAM → Task 9 ✓
- SongSpec 非法回退安全默认 → Task 2/4/5 ✓
- 中间产物落盘 → pipeline 写 outputs/、UI 展示结构化歌词 ✓
- V0.2/V0.3（Demucs/Seed-VC/repaint）明确不在本计划 ✓（Global Constraints）
- 法律免责 UI 提示 → Task 8 ✓

**Placeholder scan：** 唯一的外部对接不确定点是 ACE-Step 1.5 的确切 import/参数名（Task 6），已明确标注"以官方 README 为准，在 Colab 冒烟时校正"，并给出占位调用与冒烟验收命令——这是第三方依赖的正当集成点，非计划占位。其余步骤均含可执行代码与命令。

**Type consistency：** `SongSpec`/`VocalSpec`/`parse_spec`/`safe_spec`/`SAFE_DEFAULT_SPEC`（Task 2）→ 被 Task 4/5/6/7 一致使用；`llm.complete`（Task 3）→ Task 4/5 一致调用；`build_acestep_params`/`generate_song`（Task 6）签名与 Task 7 调用一致；`make_song` 返回键 `spec/structured_lyrics/song` 与 Task 8 使用一致。
