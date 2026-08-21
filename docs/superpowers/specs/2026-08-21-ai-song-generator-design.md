# AI 成曲 Demo — 设计文档

- 日期：2026-08-21
- 状态：设计已确认（V0.1 定稿方向），待写实现计划

## 1. 目标（一句话定义）

**一个面向音乐小白的 AI 成曲 Demo：用户只需要写歌词，并用一句话描述想要的感觉，就能生成一首完整中文歌曲；后续支持通过自然语言修改歌曲，以及用授权的参考声音进行演唱音色转换。**

真正要验证的命题不是"音色克隆技术通不通"，而是：**一个完全不会音乐软件的人，能不能很方便地把自己写的歌词变成一首还不错的歌。**

## 2. 核心原则

**专业参数是给模型的，不是给用户的。** 用户第一眼只看到：歌词、想要的感觉、一个"生成"按钮。BPM / Key / Seed / Pitch / Steps / CFG / 时长秒数 全部藏进"高级设置"，默认折叠。这是本 demo 和大多数 GitHub demo 的区别。

## 3. 关键决策（已确认）

| 维度 | 决定 |
|---|---|
| 定位 | 面向小白的消费级成曲工具 |
| 路线 | 开源自建，跑在 Colab 免费 T4 / 低成本 GPU |
| 核心模型 | **ACE-Step 1.5**（官方宣称 <4GB VRAM，支持结构化歌词/中文/BPM/Key/参考音频/repaint/remix，最长 10 分钟）— VRAM 以首跑实测为准 |
| V0.1 核心链路 | 歌词 + 一句话感觉 → **AI Song Planner** → ACE-Step 1.5 → 完整歌曲 |
| 音色转换 | Demucs + Seed-VC，**降级为 V0.3 可选功能**，默认关闭，仅用户主动开启才跑 |
| 歌曲修改 | ACE-Step repaint/remix，**V0.2**，自然语言驱动局部重做 |
| 交互 | Gradio 网页，极简 |

## 4. 版本路线图

### V0.1 — 先证明"歌词真的能成歌"（当前实现目标）
```
歌词 → 一句话感觉 → Song Planner → ACE-Step 1.5 → 完整歌曲
```
成本接近 0，Colab / 临时 GPU 就够。只有一个核心模型 + 一个很轻的 AI Planner。

### V0.2 — AI 制作人（自然语言修改）
"再来一个版本""副歌更抓耳""前奏短一点""更伤感""鼓更轻一点""重新做这 20 秒"。
核心是 ACE-Step 的 **repaint / remix**：不必重生成整首，只重做选定区段。
```
0:00 ── 1:12 ──[副歌]── 1:40 ── 3:20
用户："这段副歌更有爆发力" → repaint 只重做 1:12–1:40
```

### V0.3 — 声音玩法（"用这个声音唱"）
把 Demucs + Seed-VC 接回来，作为高级功能。UI 不写"音色转换/Seed-VC"这种术语，直接写**"用这个声音唱"**，用户上传授权的参考声音。默认关闭，点了才跑：
```
歌曲 → Demucs → 人声 → Seed-VC(零样本, 参考声10–30s) → Mixer → 新版本
```
GPU 成本只在用户真正需要时才花。

### V1.0 — 产品化（最后才考虑）
账号、作品库、历史版本、项目保存、分享、Stem 导出、MIDI、专业模式。

## 5. V0.1 架构与数据流

```
歌词 (自由文本)
风格 (一句话，如"女声，R&B，深夜，温柔")
   │
   │  ① planner   自然语言 → SongSpec (结构化)
   │  ② lyrics    自由歌词 → [Verse]/[Chorus]/... 结构化歌词
   ▼
SongSpec + 结构化歌词
   │  ③ song_gen  ACE-Step 1.5
   ▼
完整歌曲 wav
```

- **中文由 ACE-Step 1.5 保证**（`language: zh`）。
- Planner / lyrics 是很轻的文本步骤，不占 GPU（见 §9 依赖）。

### SongSpec 数据结构（planner 输出，喂给 ACE-Step）
```yaml
language: zh
vocal:
  gender: female
  style: soft
genre: [mandopop, r&b]
mood: [nostalgic, lonely, warm]
instrument: [piano, soft drums, ambient pad]
bpm: 82
structure: [Intro, Verse, Pre-Chorus, Chorus, Verse, Chorus, Bridge, Final Chorus, Outro]
```
lyrics 组件把用户的自由歌词整理成对应结构：
```
[Verse] ……
[Pre-Chorus] ……
[Chorus] ……
```

## 6. 仓库结构

```
music/
├── app.py                # Gradio 入口（极简 UI）
├── requirements.txt      # 依赖，pin 版本
├── colab.ipynb           # Colab 一键：装依赖 → 拉权重 → 启动 app(gradio share)
├── config.py             # 设备/路径/默认参数/LLM 配置
├── src/
│   ├── planner.py        # 自然语言 → SongSpec
│   ├── lyrics.py         # 自由歌词 → 结构化歌词
│   ├── song_gen.py       # ACE-Step 1.5 封装
│   └── pipeline.py       # 编排 planner → lyrics → song_gen
├── optional/             # V0.3，默认不进主链路
│   ├── separator.py      # Demucs
│   ├── voice_convert.py  # Seed-VC 零样本
│   └── mixer.py
├── assets/ref_voices/    # V0.3 内置示例参考声占位
├── outputs/              # 各阶段产物落盘
└── tests/
    ├── fixtures/
    └── test_*.py
```

## 7. 组件接口（纯函数式，可脱离 UI 单测）

```python
# src/planner.py
def plan_song(style_desc: str, *, lyrics_hint: str = "") -> dict:
    """一句话风格 → SongSpec dict（language/vocal/genre/mood/instrument/bpm/structure）。"""

# src/lyrics.py
def structure_lyrics(raw_lyrics: str, spec: dict) -> str:
    """自由歌词 + SongSpec → 带 [Verse]/[Chorus] 标签的结构化歌词字符串。"""

# src/song_gen.py
def generate_song(structured_lyrics: str, spec: dict, *,
                  length: str = "full", seed: int | None = None,
                  out_path: str) -> str:
    """结构化歌词 + SongSpec → 完整歌曲 wav。封装 ACE-Step 1.5。
       length ∈ {"short","full"} 内部映射到时长；用户不填秒数。"""

# src/pipeline.py
def make_song(raw_lyrics: str, style_desc: str, *,
              length: str = "full", seed: int | None = None,
              work_dir: str) -> dict:
    """V0.1 全链路。返回 {"spec":..., "structured_lyrics":..., "song":...}。"""

# --- optional/ (V0.3, 仅在用户开启"用这个声音唱"时调用) ---
# separator.separate(mix_wav) -> (vocal_wav, instrumental_wav)   # Demucs
# voice_convert.convert_voice(source_vocal, ref_vocal, *, pitch_shift=0) -> wav  # Seed-VC 零样本
# mixer.mix(vocal_wav, instrumental_wav) -> final_wav
```

## 8. Gradio 界面（V0.1）

第一眼只有三样东西：
```
┌─────────────────────────────┐
│  🎵 把歌词变成一首歌         │
│  歌词    [多行文本框]        │
│  你想要什么感觉？ [文本框]   │
│      [ 帮我做成一首歌 ]      │
└─────────────────────────────┘
```
- **生成中**：分步状态提示 —— 正在理解你的歌词… ✓歌词结构 ✓风格 ✓情绪 ✓人声 ✓BPM → 正在生成歌曲…
- **结果**：曲名（可留《未命名》）+ 播放器 + `[再做一个版本]` + `[下载歌曲]`
- **歌曲长度**：`○ 短版 Demo  ● 完整歌曲`（内部映射 短 30–60s / 完整 150–240s；首版甚至可只留"完整"，由模型定长）
- **高级设置（默认折叠）**：Seed / BPM / Key / Pitch / Steps / CFG —— 给想调的人，不打扰小白。
- **V0.3 高级功能（默认关闭）**：`☐ 用这个声音唱` + 上传授权音频。

## 9. 依赖与 LLM（Planner 需定）

Planner 和歌词结构化需要一个 LLM 做文本理解。这是 V0.1 唯一的新外部依赖，两种选法：

- **A. 文本 LLM API（推荐）**：调一次便宜的文本模型（如 Claude Haiku / 同级），**不占 GPU**、几乎零成本、质量稳。缺点是需网络与 key。
- **B. 本地小模型（如 Qwen 小尺寸）**：完全自建、离线，但要额外占显存/加载时间，和"省钱省事"目标略冲突。

推荐 **A**，并在 `config.py` 做成可切换，后续想完全离线再换 B。**待用户确认。**

> ACE-Step 1.5 / Demucs / Seed-VC 权重首次运行下载并缓存到持久目录；版本在 `requirements.txt` 里 pin 死。

## 10. 错误处理

- **OOM**：捕获后 UI 友好提示（选"短版"/减步数/换更大 GPU），不静默失败。ACE-Step 1.5 号称 <4GB，但首跑实测确认。
- **权重/依赖缺失**：启动时检查，缺失给下载指引，不拖到生成时才报错。
- **Planner 输出不合法**：SongSpec 用固定 schema 校验，LLM 返回不合规时回退到一组安全默认值（中性流行、中速、常见结构），保证链路不断。
- **各阶段产物落盘** `outputs/`，UI 可试听，便于定位。
- **V0.3 参考声太脏**：提示选人声清晰段落，可改选/关闭。

## 11. 测试策略

- **组件级 smoke test**
  - `planner`：给一句话风格，返回合法 SongSpec（字段齐、类型对、bpm 合理）。
  - `lyrics`：给几行自由歌词，返回带 `[Verse]/[Chorus]` 标签的字符串。
  - `song_gen`：给极短结构化歌词 + 最小 spec，产出非空 wav。
  - （V0.3）`separator`/`voice_convert`/`mixer` 各自 smoke test。
- **链路级**：`make_song` 用最短歌词跑通，断言 spec / structured_lyrics / song 三个产物齐全。
- **手动验收**：Gradio 输入真实中文歌词 + 一句话感觉，主观试听。

## 12. 部署路线

1. **Colab 起步**：`colab.ipynb` 装依赖 + 拉权重 → 跑 `app.py` 用 `gradio share` 出公网链接，零成本验证 V0.1。
2. **迁移 Runpod/AutoDL**：`config.py` 设备/路径/权重/LLM 全可配，效果确认后迁常驻 GPU。

## 13. 法律与伦理边界

音色转换（V0.3）克隆真实歌手涉及声音权/肖像权。demo 定位为技术演示：优先自己或已授权的声音；克隆他人仅限私下演示，不对外发布或商用。相关 UI 加一句免责提示。
```
