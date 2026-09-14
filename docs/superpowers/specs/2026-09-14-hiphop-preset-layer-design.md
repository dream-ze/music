# ze music — 出歌质量与 hip hop 风格：输入链重建（风格 Preset 层）设计

- 日期：2026-09-14
- 状态：设计已确认，待写实现计划
- 前置：第 0 层修复已完成并实测（见 §2）

## 1. 背景与目标

使用方反馈三个问题：**(1) 吐字不清晰；(2) 音色不丰富、AI 感重；(3) 想重点做 hip hop 风。**

排查结论：三个问题的根都在同一条链上 —— **我们喂给 ACE-Step 的 caption / 歌词 / 元数据的质量**。实测证明 ACE-Step 的 5Hz LM 是一个忠实的扩写器：给它 `mandopop, warm, piano…` 它就规划成女声抒情电子流行；给它 `Hip Hop, Rap…` 它就规划成 lo-fi 说唱。它**不会**替我们纠正 caption 与歌词之间的冲突（官方文档亦明确"模型不擅长解决冲突"）。

本设计的目标：把这条输入链重建到官方示例的水准，并用一个**风格 Preset 层**承载 hip hop 的领域知识，使其可扩展到其他风格。

**成功标准**（固定 seed A/B，同词同 seed 只换输入链）：
- 吐字：断行后每行 ≤ 10 音节（LLM 路径目标 6–10；确定性回退不合并短行），主观评分（1–5）相对基线提升；
- 风格：选择 hip hop preset 时，DiT 实际收到的 caption 含 rap/808/hi-hat 等风格词，bpm 落在 preset 区间，结构使用 `[Hook]`；
- 音色：caption 覆盖官方九维，且携带 `keyscale` / `timesignature`。

## 2. 已完成的前置工作（第 0 层，2026-09-14）

以下问题已修复并有测试覆盖，本设计以其为基础：

| 问题 | 修复 |
|---|---|
| 5Hz LM 从未初始化（配置指向未下载的 0.6B；`initialize()` 返回 `(msg, False)` 被丢弃） | 两个 `initialize*` 返回值均检查，失败抛 `RuntimeError`；失败不写全局缓存 |
| planner / 歌词整理静默回退，界面无区别 | 事件结构化 `{"stage", "ok"}`，落库 `songs.llm_status`，前端「降级」标记 |
| `_fallback()` 把已带标记的歌词再包一层（标记重复、整段复制、多出冲突的 `[Chorus]`） | 单独成行的 `[xxx]` 视为已有结构，原样透传 |
| 供应商写死 anthropic | `config.LLM_PROVIDER`（默认 anthropic），`make_song` 默认使用 |
| 本机 16GB 统一内存装不下 turbo + 1.7B LM（MPS OOM，与时长无关） | `ACESTEP_OFFLOAD` / `ACESTEP_LM_BACKEND` 开关；本机 `.env` 用 0.6B + pt + offload，实测出歌成功 |

**硬件结论**：本机只能跑 turbo 8 步 + 0.6B LM（开发迭代档）。SFT 50 步 + CFG + 1.7B/4B（音色天花板）只能上云，**不在本设计范围**。

## 3. 范围

### 3.1 做

1. 风格 Preset 层（数据驱动），首批 `hiphop.boom_bap`、`hiphop.trap`，加 `generic` 兜底；
2. planner 输出契约升级：英文整句 caption + `keyscale` + `timesignature`，CJK 硬校验；
3. 歌词断行器：只断行、不改字（逐字相等硬校验），已带标记的歌词同样断行；
4. `vocal_language` 合法化与混合语言策略；
5. `song_gen` 传递 caption / keyscale / timesignature / `use_cot_caption` / shift；
6. API `Overrides.preset`；前端 preset 选择、风格 chips 改发英文 tag、灵感示例加 hip hop；
7. 降级事件增加 `reason`，前端显示；
8. 评测循环文档（固定 seed A/B 流程与打分表）。

### 3.2 不做（明确排除）

- 换模型档位 / SFT / CFG / 更大 LM / 上云（阶段 3，单独讨论）；
- 参考音频风格迁移（版权问题）；
- 改写、增删用户歌词的**字**；AI 代写歌词；
- LoRA 微调；
- planner 自动推断 preset（首期 preset 仅由 UI 选择；未选则 `generic`）。

## 4. 架构

```
用户: 歌词 + 感觉 + [preset]
        │
        ▼
planner (DeepSeek)  ←── Preset(骨架/词池/规则/官方句式示例)
   输出 SongSpec: caption(英文整句)/genre/mood/instrument/bpm/keyscale/timesignature/structure/vocal/language
   校验: CJK 硬校验 → 违规回退 preset 英文骨架(事件 ok=false, reason)
        │
        ▼
lyrics 断行器 (DeepSeek)  ←── Preset.lyric_rules
   校验: normalize(输入)==normalize(输出) → 违规回退确定性断行(事件 ok=false, reason)
   结构标签: 用户已有 → 保留;无 → 按 Preset.structure 补;Verse 段追加 vocal 限定词
        │
        ▼
song_gen → GenerationParams(caption, lyrics, bpm, keyscale, timesignature,
           vocal_language, shift, use_cot_caption=not spec.caption_full, thinking=True)
        │
        ▼
ACE-Step (turbo + 5Hz LM)
```

## 5. 组件设计

### 5.1 Preset 层 — `src/presets.py`

pydantic 模型 `Preset` + 注册表 `PRESETS: dict[str, Preset]`。**数据，不是代码分支**：新增风格只加一条数据。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | str | 如 `hiphop.boom_bap` |
| `label` | str | 中文显示名 |
| `family` | str | `hiphop` / `generic`，前端分组 |
| `caption_skeleton` | str | 英文整句模板，含 `{instruments}` `{texture}` `{vocal}` 等占位 |
| `instrument_pool` / `texture_pool` / `era_pool` | list[str] | 词池，planner 从中选取；`generic` 的池为空表示不限 |
| `bpm_range` | (int, int) | boom bap (85, 95)；trap (130, 150) |
| `keyscale_hint` | str | 如 `minor`；planner 据此选具体调 |
| `timesignature` | int | 4 |
| `structure` | list[str] | `["Intro","Verse","Hook","Verse","Hook","Outro"]` |
| `vocal_qualifier` | str | Verse 段限定词，如 `rap`；空则不加 |
| `vocal_gender_default` | str | `male`（用户/planner 可覆盖） |
| `lyric_rules` | `LyricRules` | `min_syllables=6, max_syllables=10, tolerance=2` |
| `acestep` | `AceStepKnobs` | `shift`（默认 3.0）、`vocal_language_policy`（见 5.4） |
| `examples` | list[str] | 1–2 条官方风格的英文 caption 示例，注入 planner 提示词 |

首批数据：
- `generic`：骨架为通用九维句式；池为空；`structure` 为现有默认；`vocal_qualifier` 空；bpm (60, 160)。
- `hiphop.boom_bap`：bpm (85, 95)；池含 `dusty drum break, boom bap drums, upright bass, jazzy piano sample, vinyl crackle, warm, gritty, 90s`；示例取自官方 `example_100` 的句式。
- `hiphop.trap`：bpm (130, 150)；池含 `808 sub-bass, rolling hi-hats, trap drums, dark synth pads, vocal chops, punchy, modern`；示例取自官方 `example_118` 的句式。

`get_preset(id) -> Preset`：未知 id 抛 `ValueError`（API 层转 422）；空 id 返回 `generic`。

### 5.2 `SongSpec` 扩展 — `src/spec.py`

新增字段（均有默认值，向后兼容已落库的 `spec_json`）：

| 字段 | 类型 | 默认 | 约束 |
|---|---|---|---|
| `caption` | str | `""` | ≤ 512 字符（ACE-Step 上限）；**不得含 CJK 字符** |
| `caption_full` | bool | `False` | caption 是否为 planner 产出的完整整句（决定 `use_cot_caption`） |
| `keyscale` | str | `""` | 形如 `F minor` / `A♭ major`；空表示交给 LM |
| `timesignature` | int \| None | `None` | 2/3/4/6 |
| `preset_id` | str | `"generic"` | |
| `language` | str | `"zh"` | 必须 ∈ {`zh`,`en`,`yue`,`unknown`}（经 5.4 归一化后） |

`genre` / `mood` / `instrument` 同样**不得含 CJK 字符**。

校验只作用于 **planner 输出与 API overrides**；读取已落库的旧 `spec_json`（含今天存下的 `zh-en`）不做校验，前端仍按原样展示，避免历史数据变成解析错误。

**CJK 硬校验**：`has_cjk(s)` = 存在码点落在 `一-鿿`、`㐀-䶿`、`　-〿`、`＀-￯` 任一区间。校验失败时 `parse_spec` 抛 `ValueError`，planner 据此回退。

### 5.3 planner — `src/planner.py`

提示词注入：preset 的骨架、词池、bpm 区间、结构、`examples`，以及官方九维提示（风格/情绪/乐器/质感/年代/制作/人声/速度/结构）。要求输出**仅 JSON**，`caption` 为 1–3 句英文。

回退策略（与今天不同：不再回退到硬编码 mandopop）：
1. LLM 调用失败 / JSON 解析失败 / `parse_spec` 校验失败 → 用 preset 渲染骨架：`caption_skeleton` 以池中前 N 项填充，bpm 取区间中点，structure/vocal 取 preset 默认，`caption_full=False`；
2. 事件：`{"stage": "歌曲规划", "ok": False, "reason": <"llm_error" | "bad_json" | "non_english" | "invalid_spec">}`。

用户 overrides（genre/mood/vocal_gender/language）仍在 planner 之后覆盖；overrides 中的 genre/mood 由前端保证为英文 tag（§5.7）。

### 5.4 `vocal_language` 归一化

planner 可能输出 `zh-en`、`Chinese` 等。归一化函数 `normalize_language(raw, policy) -> str`：
- 含 `zh`/`chinese`/`mandarin` 且含 `en`/`english` → 混合 → 取 `policy`（preset 的 `vocal_language_policy`，首批全部为 `"zh"`，A/B 时可改 `"unknown"`）；
- 单一且 ∈ {`zh`,`en`,`yue`} → 原值；`cantonese` → `yue`；
- 其余 → `unknown`。

保持 `use_cot_language=True` 让 LM 兜底。

### 5.5 歌词断行器 — `src/lyrics.py`

职责由"分段加标签"改为"**断行 + 补标签**"，且对已带标记的歌词同样生效。

**音节计数** `syllables(line) -> int`：
- 每个 CJK 字符 = 1；
- 每个英文单词：统计元音组 `[aeiouy]+` 个数，最少 1；单词长度 > 2 且以 `e` 结尾、不以 `le` 结尾时减 1；
- 标点、数字、空白不计。

**LLM 步骤**：提示词给出规则（每行 `min`–`max` 音节；同段同位置行 ±`tolerance`；只可移动换行、不可增删改任何字；保留所有 `[标签]` 行与段间空行），输出纯文本。空响应重试一次。

**硬校验** `same_text(a, b)`：`normalize(a) == normalize(b)`，其中 `normalize` = 删除所有空白字符与所有单独成行的 `[...]` 标签行。**不相等即丢弃 LLM 输出**。

**确定性回退** `split_long_lines(text, max)`：对音节数 > `max + tolerance` 的行，先在中英文标点（`，。、；！？,.;!?`）处切，仍超则在空格 / CJK 字符边界处切至 ≤ `max`；不足 `min` 的短行不合并（合并会改变用户的断句意图）。

**结构标签**：
- 用户歌词已有单独成行的 `[...]` → 全部保留，不增不删；
- 没有 → 按 `Preset.structure` 顺序为各段补标签（段以空行分隔；段数少于结构长度时按顺序取前 N 个，多于则最后一个标签复用）；
- `Preset.vocal_qualifier` 非空时，对**无 `-` 限定词的 `[Verse…]` 标签**改写为 `[Verse - <qualifier>]`；`[Hook]`/`[Chorus]` 不动（官方警告勿堆叠标记）。

事件：`{"stage": "歌词整理", "ok": bool, "reason": <"llm_error" | "empty" | "text_changed" | None>}`；`ok=False` 时仍输出确定性回退结果（可用，但被标记降级）。

### 5.6 `song_gen` — `src/song_gen.py`

`build_acestep_params(spec, …)` 输出新增：`caption`（`spec.caption` 非空则用之，否则回退标签串）、`keyscale`、`timesignature`、`use_cot_caption = not spec.caption_full`、`shift`（优先级：环境变量 `ACESTEP_SHIFT` > `preset.acestep.shift` > 3.0）。`vocal_language` 为归一化值。`thinking=True` 不变；`inference_steps=8` 不变。

### 5.7 API 与前端

- `server/models.py`：`Overrides.preset: str = ""`；`genre`/`mood` 期望英文 tag（服务端对 CJK 值做 422 拒绝，避免再次混入）。
- `web/components/AdvancedSettings.tsx`：
  - 新增「风格预设」分段控件：自动（`generic`）/ Boom Bap / Trap；
  - 风格 chips 改为 `{label: "流行", tag: "pop"}` 形式，**显示中文、发送英文**；情绪 chips 同理；
  - 新增 chip「Hip hop」（tag `hip hop`），选中时若未选 preset 则默认 `hiphop.boom_bap`。
- `web/lib/types.ts`：`overrides.preset?: string`。
- `server/inspirations.py` / `InspirationList`：新增一条 hip hop 示例（使用 2026-09-14 用户提供的中英混合说唱歌词），`onPick` 同时设置 `preset`。
- `SongCard` 降级标记 title 追加 `reason` 的中文映射（如「歌词整理：模型改动了歌词，已用规则断行」）。

### 5.8 环境开关（阶段 2 调参用，本期只提供开关）

| 变量 | 默认 | 作用 |
|---|---|---|
| `ACESTEP_SHIFT` | 3.0 | 覆盖 shift |
| `ACESTEP_CONFIG` | `acestep-v15-turbo` | 已有；可换 `turbo-shift1` 等变体 |
| `ACESTEP_OFFLOAD` / `ACESTEP_LM_BACKEND` / `ACESTEP_LM_MODEL` | 见第 0 层 | 已有 |

## 6. 错误处理与可见性

原则延续第 0 层：**链路上任何降级都必须显式**。

| 情形 | 行为 | 用户可见 |
|---|---|---|
| planner 失败 / 非英文 / 校验失败 | 回退 preset 骨架，继续出歌 | 「降级」标记 + reason |
| 断行器改了字 / 空响应两次 | 回退确定性断行，继续出歌 | 「降级」标记 + reason |
| 未知 preset id | 422 | 表单报错 |
| overrides 含 CJK | 422 | 表单报错 |
| ACE-Step 初始化失败 | 抛错，任务 error | 任务失败提示（第 0 层已做） |

## 7. 测试策略（TDD，每项先红后绿）

- `test_presets.py`：注册表含三项；`get_preset("")` → generic；未知 id 抛错；每个 preset 的骨架/池/示例**不含 CJK**；bpm 区间合法。
- `test_spec.py`：CJK 校验对 caption/genre/mood/instrument 生效；`language` 枚举；旧 `spec_json`（无新字段）仍可解析。
- `test_planner.py`：提示词包含 preset 骨架与示例；输出含 CJK → 回退骨架且 reason=`non_english`；bad JSON → reason=`bad_json`；骨架回退产出的 caption 不含 CJK、bpm 在区间内。
- `test_lyrics.py`：`syllables` 对中文/英文/混合行；LLM 改字 → 丢弃并 reason=`text_changed`；空响应重试一次；确定性切分在标点优先；已带标签歌词保留全部标签并仍被断行；无标签歌词按 preset 结构补标签；`[Verse]` → `[Verse - rap]`、`[Hook]` 不动。
- `test_song_gen.py`：`build_acestep_params` 传递 caption/keyscale/timesignature；`use_cot_caption` 与 `caption_full` 相反；`ACESTEP_SHIFT` 覆盖。
- `test_pipeline.py`：preset 贯穿 planner→lyrics→song_gen；`degraded` 与 reason 汇总。
- `test_api.py`：`preset` 透传；未知 preset / CJK overrides → 422。
- 前端 `vitest`：preset 控件发送 id；chips 发送英文 tag；灵感示例带 preset；降级 title 含 reason 文案。

## 8. 评测循环

文档 `docs/superpowers/evals/hiphop-ab.md`，记录每次 A/B：

| 字段 | 说明 |
|---|---|
| seed | 固定（如 `1001, 1002, 1003`） |
| 变量 | 只改一项：caption 骨架 / 断行 / `vocal_language` / shift |
| 输入 | 同一段词（首期用 2026-09-14 的中英说唱词） |
| 评分 | 吐字 / 音色 / 风格，各 1–5，两人独立打分取均值 |
| DiT 实际 caption | 从 `backend.log` 的 LM CoT 段抽取，与我们传入的对照 |

本机 0.6B 用于迭代；阶段 3 上云后用同一套词与 seed 复跑对比。

## 9. 决策记录

| 决策 | 结论 | 理由 |
|---|---|---|
| 范围形态 | Preset 层，hip hop 先做 | 可扩展；其他风格只加数据 |
| 歌词 | 只断行不改字，逐字相等硬校验 | 尊重用户作品；机器可验证 |
| 混合语言 | 默认 `zh`，A/B `unknown` | 官方中文 hip hop 示例做法；ACE-Step 无 `zh-en` |
| `use_cot_caption` | 有完整英文 caption 时关，降级时开 | DeepSeek 音乐知识 ≫ 本机 0.6B |
| 首批子风格 | boom bap + trap | YAGNI；lo-fi 作 boom bap 的质感变体 |
| planner 回退目标 | preset 英文骨架，而非硬编码 mandopop | 降级也要在正确风格上 |
| 模型档位升级 | 移出本期，阶段 3 上云 | 16GB 统一内存实测装不下 |
| 参考音频 | 不做 | 版权 |

## 10. 阶段划分

| 阶段 | 位置 | 内容 | 对应问题 |
|---|---|---|---|
| 1（本 spec） | 本机 | §3.1 全部 | 1、3 主体；2 的输入链部分 |
| 2 | 本机 | 用 §5.8 开关做 shift / 变体 / `vocal_language` A/B | 2 的免费部分 |
| 3 | 云 GPU | SFT 50 步 + CFG + 1.7B/4B；可选参考音频 | 2 的天花板 |

## 11. 触及文件（阶段 1）

后端：`src/presets.py`（新）、`src/spec.py`、`src/planner.py`、`src/lyrics.py`、`src/song_gen.py`、`src/pipeline.py`、`server/models.py`、`server/routes.py`、`server/inspirations.py`、对应 `tests/`。
前端：`web/components/AdvancedSettings.tsx`、`GenerateForm.tsx`、`InspirationList.tsx`、`SongCard.tsx`、`web/lib/types.ts`、`web/test/`。
文档：`docs/superpowers/evals/hiphop-ab.md`（新）。
