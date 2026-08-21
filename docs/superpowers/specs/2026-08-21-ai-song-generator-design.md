# AI 歌词成曲 Demo — 设计文档

- 日期：2026-08-21
- 状态：设计已确认，待写实现计划

## 1. 目标

一个 Gradio 网页 demo：用户输入**歌词**和**风格描述**，系统自动**作曲 + 编曲 + 演唱**，产出一首完整的中文歌曲；并可**导入一首参考歌曲**，把生成歌曲的人声**音色转换**成参考歌曲里歌手的嗓音（零样本，不用训练）。全部基于开源模型自建，不依赖商业 API。

### 成功标准
- 输入一段中文歌词 + 一句风格描述（如"周杰伦风格的中国风 R&B"），几分钟内生成一首可试听的完整歌曲（含人声与伴奏）。
- 上传/选择一首参考歌曲，一键把成品人声换成该歌手音色，网页可试听并下载。
- 整条链路在 Colab（免费 T4 或低成本 GPU）上能跑通。

## 2. 关键决策（已确认）

| 维度 | 决定 |
|---|---|
| 路线 | 开源自建 |
| 算力 | 云 GPU（先 Colab 起步，后续可迁 Runpod/AutoDL） |
| 语言 | 中文为主（模型多语言，参数按中文调） |
| 交互 | Gradio 网页 |
| 生成粒度 | 端到端出歌 + 音色转换 |
| 音色克隆 | **导入参考歌曲 → Demucs 抠人声 → Seed-VC 零样本转换（不训练）**；RVC 训练作为可选高质量模式，后置 |
| 首版音色 | 内置 1–2 个示例参考音频占位，同时开放上传入口 |

## 3. 架构与数据流

### 3.1 主生成链路

```
歌词 + 风格标签
   │  ① song_gen(ACE-Step)   端到端生成整首歌（旋律 + 编曲 + 人声）
   ▼
整首歌（混音 wav, 44.1k）
   │  （若不启用音色转换，直接作为成品）
   │  ② separator(Demucs v4)  分离 → 人声轨 / 伴奏轨
   ▼
生成人声轨 ──③ voice_convert(Seed-VC)──▶ 换成参考音色 ─┐
生成伴奏轨 ────────────────────────────────────────────┤ ④ mixer  对齐+增益+导出
                                                        ▼
                                                    成品歌曲 wav
```

### 3.2 音色参考的准备（导入歌曲 → 参考音色片段）

零样本方案下**没有"训练"步骤**，只需要一段干净的参考人声：

```
参考歌曲（用户上传/内置示例）
   │  separator(Demucs)  抠出人声
   │  取其中一段清晰的副歌/主歌（10–30s 即可）
   ▼
参考音色片段 ref_vocal.wav  ← 直接喂给 ③ voice_convert 做零样本转换
```

- **中文由 ① 保证**：咬字发音来自 ACE-Step 的中文人声；③ 只换音色，对语言不敏感。
- **音色转换是链路，不是一步**：端到端模型输出的是混好的整首歌，必须先分离人声，才能对人声单独换音色，再与原伴奏混回。
- **共用 Demucs**：主链路分离生成人声、参考准备分离参考人声，是同一个 `separator` 组件。

### 3.3 可选高质量模式（RVC 训练，后置迭代，非首版必做）

`参考人声(多首更好, ≥10min) → 切片+去噪 → 提取F0+HuBERT特征 → 训练(GPU 15–60min) → 音色.pth + .index → 替换 ③ 的 Seed-VC`。首版只留入口与文档，不实现训练 UI。

## 4. 模型选型

| 环节 | 首选 | 仓库 | 显存/规模 | 备选 |
|---|---|---|---|---|
| 端到端出歌 | **ACE-Step** | `ace-step/ACE-Step`（Apache 2.0） | ~15GB（可量化/降配跑更小） | YuE（更强更慢）、DiffRhythm（极快） |
| 人声/伴奏分离 | **Demucs v4** (htdemucs) | `facebookresearch/demucs` | ~4GB | UVR5 |
| 零样本音色转换 | **Seed-VC**（含歌声转换模式） | `Plachtaa/seed-vc` | ~4–6GB | RVC（需训练）、So-VITS-SVC |
| 前端 | **Gradio** | — | — | — |

> 版本需在 Colab 里 pin 死，避免依赖漂移。ACE-Step 与 Seed-VC 都需要在首次运行时下载权重（几 GB），Notebook 里缓存到持久目录。

## 5. 仓库结构

```
music/
├── app.py                    # Gradio 入口
├── requirements.txt          # 依赖（pin 版本）
├── colab.ipynb               # Colab 一键：装依赖 → 拉权重 → 启动 app（gradio share）
├── config.py                 # 设备(cuda/mps/cpu)、路径、默认参数、模型权重位置
├── src/
│   ├── song_gen.py           # ACE-Step 封装
│   ├── separator.py          # Demucs 封装
│   ├── voice_convert.py      # Seed-VC 封装
│   ├── mixer.py              # 混音
│   └── pipeline.py           # 编排 ①→②→③→④
├── assets/
│   └── ref_voices/           # 内置示例参考音频（占位音色）
├── outputs/                  # 各阶段产物落盘（可试听/定位问题）
└── tests/
    ├── fixtures/             # 短歌词、短音频测试素材
    └── test_*.py             # 组件级 + 链路级 smoke test
```

## 6. 组件接口（各自单一职责、纯函数式、可脱离 UI 单测）

```python
# src/song_gen.py
def generate_song(lyrics: str, style_prompt: str, *,
                  duration_sec: int = 90, seed: int | None = None,
                  out_path: str) -> str:
    """歌词+风格 → 整首歌 wav 路径。封装 ACE-Step。"""

# src/separator.py
def separate(mix_wav: str, *, out_dir: str) -> tuple[str, str]:
    """混音 wav → (vocal_wav, instrumental_wav)。封装 Demucs htdemucs。"""

# src/voice_convert.py
def convert_voice(source_vocal: str, ref_vocal: str, *,
                  pitch_shift: int = 0, out_path: str) -> str:
    """源人声 + 参考人声 → 换音色后的人声 wav。零样本 Seed-VC，无需训练。"""

# src/mixer.py
def mix(vocal_wav: str, instrumental_wav: str, *,
        vocal_gain_db: float = 0.0, out_path: str) -> str:
    """人声 + 伴奏 → 对齐+增益+导出成品 wav。"""

# src/pipeline.py
def make_song(lyrics: str, style_prompt: str, *,
              ref_song: str | None = None,   # 参考歌曲(整首)，None=不换音色
              duration_sec: int = 90, seed: int | None = None,
              work_dir: str) -> dict:
    """
    编排全链路，返回各阶段产物路径：
    {"raw_song":..., "vocal":..., "instrumental":...,
     "converted_vocal":..., "final":...}
    ref_song 为 None 时跳过 ②③④，final = raw_song。
    ref_song 非 None 时：先对 ref_song 跑 separator 取参考人声片段。
    """
```

## 7. Gradio 界面布局（`app.py`）

单页，分区：

- **输入区**
  - 歌词文本框（多行）
  - 风格描述文本框（占位示例："中国风 R&B，钢琴+弦乐，深情男声，90 BPM"）
  - 时长滑块（30–180s，默认 90）、随机种子（可选）
- **音色区**
  - 开关："启用音色转换"
  - 参考来源：下拉选内置示例 / 上传参考歌曲（音频文件）
  - 变调滑块 pitch_shift（男女声跨性别时用，默认 0）
- **操作**：`生成` 按钮（禁用态防重复点击）
- **结果区（分阶段试听，便于定位）**
  - 原始生成歌曲（player）
  - 分离人声 / 分离伴奏（player，折叠）
  - 换音色后人声（player）
  - **成品**（player + 下载按钮）
- **状态/日志区**：显示当前阶段与耗时；OOM/缺权重等错误友好提示。

## 8. 参数默认值与耗时估算（Colab T4 量级，供预期管理）

| 阶段 | 默认参数 | 估算耗时（90s 歌，T4） |
|---|---|---|
| ACE-Step 出歌 | duration=90s, steps 默认 | 约 0.5–3 分钟 |
| Demucs 分离 | htdemucs, 2-stem | 约 20–60 秒 |
| Seed-VC 转换 | 零样本, pitch=0 | 约 20–60 秒 |
| 混音导出 | gain=0 | 秒级 |

> T4 上 ACE-Step 可能需要开启显存优化/降低步数；若 OOM，UI 提示降低时长或换更大 GPU。

## 9. 错误处理

- **显存不足 (OOM)**：捕获后 UI 明确提示"降低时长 / 减少步数 / 换更大 GPU"，不静默失败。
- **权重缺失**：启动时（`config.py`/notebook）检查权重文件，缺失给下载指引，不拖到生成时才报错。
- **参考人声太脏**：分离残留伴奏会劣化音色——UI 提示"参考尽量选人声清晰段落"；允许用户改选/上传其它参考。
- **音色转换失败/不满意**：可关闭音色转换，直接用 ACE-Step 原版人声作为成品。
- **中间产物落盘**：每步产物存 `outputs/` 并在 UI 可试听，任一步出问题都能定位。

## 10. 测试策略

- **组件级 smoke test**：每个封装模块用 `tests/fixtures/` 里的短音频/短歌词跑一次，断言输出文件存在、采样率/时长合理。
  - `song_gen`：给极短歌词，产出非空 wav。
  - `separator`：给一段带人声的短音频，产出两个非空轨。
  - `voice_convert`：给源人声+参考人声，产出非空 wav 且时长≈源。
  - `mixer`：两轨 → 一轨，时长≈较长轨。
- **链路级**：`make_song` 用最短歌词 + 内置示例参考跑通，断言五个产物路径都存在。
- **手动验收**：Gradio 里输入真实中文歌词 + 风格 + 参考歌曲，主观试听。

## 11. 明确不做（YAGNI）

- 首版不实现 RVC 在线训练 UI（只留入口 + 文档），高质量模式后置迭代。
- 不做分阶段可控作曲（MIDI 旋律→逐轨编曲→DiffSinger 逐字合成）——太重、质量不占优。
- 不做账号、云存储、分享社区等产品化功能。
- 不做本地 Mac 跑重模型（硬约束：需 CUDA）。

## 12. 部署路线

1. **Colab 起步**：`colab.ipynb` 装依赖 + 拉权重 → 跑 `app.py` 用 `gradio share` 出公网链接，零成本验证整条链路。
2. **迁移 Runpod/AutoDL**：`config.py` 把设备/路径/权重位置都做成可配置，效果确认后迁到常驻 GPU 做稳定演示。

## 13. 法律与伦理边界

音色克隆真实歌手涉及声音权/肖像权。demo 定位为**技术演示**：优先用自己的或已授权的声音；克隆他人音色仅限私下演示，不对外发布或商用。UI 中加一句免责提示。
