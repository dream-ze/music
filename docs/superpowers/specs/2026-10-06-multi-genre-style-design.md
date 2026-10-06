# ze music — 多曲风与人声音色：风格库 + 采样器 设计

- 日期：2026-10-06
- 状态：设计草案，待确认后写实现计划
- 前置：[2026-09-14 风格 Preset 层](2026-09-14-hiphop-preset-layer-design.md)（已实现）

## 1. 背景与目标

使用方反馈：**生成的歌曲风和音色太单一**。

排查结论（证据来自 `ze_music.db` 最近 7 首的 `spec_json`）：问题主要在输入链，不在模型能力。

| # | 根因 | 证据 / 位置 |
|---|---|---|
| R1 | 前端选的曲风 / 情绪**没进 planner**，只在 planner 之后覆盖 `spec.genre`；而 planner 产出完整 caption 时 DiT 只看 caption（`use_cot_caption=False`），`genre` 被无视 | `src/pipeline.py:41`；09-30 一首选了 Hip hop，caption 却是 "indie folk… fingerpicked acoustic guitar… cello" |
| R2 | 「感觉」多数为空，`generic` 只有**一条**示例（warm 钢琴抒情 + airy pads + intimate 女声），planner 照抄 | generic 歌的 caption 反复出现 warm / soft piano / pads / intimate |
| R3 | 只有 3 个 preset（2 个是 hip hop）；planner 把词池**整池照抄**，同 preset 的 caption 几乎逐字相同 | boom bap 4 首 caption 前 160 字几乎一致 |
| R4 | 人声只有 "confident, articulate" 这类泛词，没有音色维度 | `VocalSpec.style` |

**目标**：同一段歌词能稳定生成**听得出差别**的多种曲风与音色；用户选了什么，最终 caption 就一定是什么。

**成功标准**（§8 评测网格：同词 × 14 曲风 × 固定 seed）：
- 曲风命中：caption 含所选曲风关键词的比例 = 100%（校验保证）；
- 多样性：两两 caption 的词集 Jaccard 均值 < 0.25（基线待测，预期 > 0.5）；
- 同曲风内多样性：同曲风不同 seed 的乐器组合不完全相同；
- 盲听：评审能分辨曲风的比例 ≥ 80%；
- 可复现：同 seed + 同输入 → 同一采样结果。

## 2. 参考来源

| 来源 | 许可 | 借鉴 |
|---|---|---|
| [ddv1982/suno-prompting](https://github.com/ddv1982/suno-prompting) | MIT | 曲风数据结构：乐器**按编曲角色分池**（harmonic / color / movement / rare），每池 `pick{min,max}`、rare 池 `chanceToInclude`；`exclusionRules` 互斥对；`bpm{min,max,typical}`；genre-aware moods；曲风识别「关键词 → LLM」；创意度档位 |
| ACE-Step `examples/text2music/`（200 条） | MIT | 官方完整 caption，覆盖 40+ 曲风，人声描写具体 → 按曲风检索做 few-shot |
| ACE-Step [Tutorial.md](https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/Tutorial.md) | MIT | caption 九维；"描述越细自由度越低"；"避免冲突词"；冲突转为时间上的演进；歌词段落标签可控制演唱方式 |
| [daveshap/suno](https://github.com/daveshap/suno) | — | 段落标签修饰词（`[Whispered Pre-Chorus]`）→ 段内音色变化 |
| [strnad/HeartMuse](https://github.com/strnad/heartmuse) | — | 逐字段「AI 生成 / 锁定」的交互思路 |

数据改编自 suno-prompting 的部分在文件头注明出处与 MIT 声明。suno 标签词典、awesome-suno-prompts 等**不搬运**（许可不明 / 含推广）。

## 3. 范围

### 3.1 做

1. 风格库：Preset 结构升级（角色分池 / 互斥 / 识别关键词 / 校验词 / 融合伙伴），首批 14 个曲风；
2. 人声音色表：11 项，含段落修饰；
3. 采样器 `src/style_sampler.py`：确定性（seed）、互斥、防重复、创意度三档；
4. 示例库：官方 200 条打标 → `src/data/caption_bank.json`，按曲风检索；
5. planner：用户选择与采样结果作为**硬约束**进提示词；检索示例；caption 校验 + 重试 + 回退（修 R1/R2）；
6. 曲风识别：未选曲风时从「感觉」识别，识别不出则随机；
7. 歌词：按音色给段落标签加修饰（只动标签行）；
8. 服务端在 seed 为空时生成 seed 并落库；
9. API `overrides.vocal_timbre` / `overrides.creativity`；前端曲风网格、音色选择、「换一种」、结果卡展示风格摘要；
10. 评测网格脚本与记录文档。

### 3.2 不做

- LoRA、参考音频、换模型档位（另行评估）；
- 改用户歌词的字（沿用逐字相等硬校验）；
- 多曲风自由组合（融合仅限数据里预设的伙伴对）；
- 批量出歌（受 16GB 内存约束，另行实测）。

## 4. 架构

```
用户: 歌词 + 感觉 + [曲风] + [情绪] + [性别] + [音色] + [创意度] + [seed]
        │
        ▼
① 曲风解析  resolve_genre(): UI 选择 > 感觉关键词 > LLM 识别 > 随机(避开最近 N 首)
        │
        ▼
② 采样器    sample_style(preset, locks, seed, creativity, recent)
            → StyleDraw{instruments, textures, era, moods, vocal_timbre, bpm, fusion?}
        │
        ▼
③ planner   提示词 = 硬约束(StyleDraw + 用户锁定项) + 检索示例(2–3 条) + 九维规则
            校验 caption: 曲风词 ∧ 音色词 ∧ 无冲突词 ∧ 无 CJK
            失败 → 带错误重试 1 次 → 仍失败 → render_skeleton(StyleDraw)
        │
        ▼
④ 歌词      断行(不改字) + 结构标签 + 音色段落修饰
        │
        ▼
⑤ song_gen  (不变) caption / keyscale / timesignature / shift / seed
```

关键变化：**采样在 planner 之前**，planner 只负责把抽好的要素写成好句子，不再自己挑词。同一 seed 下 ①② 确定，③ 的措辞由 LLM 决定。

## 5. 组件设计

### 5.1 风格库 — `src/presets.py`

`Preset` 升级（旧字段保留兼容，新字段均有默认值）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` / `label` / `family` | str | 不变；`family` 用于前端分组 |
| `keywords` | list[str] | 识别用，中英文都写（如 `["民谣","folk","acoustic"]`） |
| `caption_keywords` | list[str] | 校验用：最终 caption 必须命中其中至少一个（英文，小写匹配） |
| `avoid` | list[str] | 冲突词：caption 出现即校验失败（如民谣避开 `808`、`dubstep`） |
| `instrument_pools` | dict[str, Pool] | 角色 → `Pool{items, pick_min, pick_max, chance=1.0}`；角色取 `harmonic` / `color` / `rhythm` / `rare` |
| `exclusions` | list[tuple[str,str]] | 互斥对 |
| `texture_pool` / `era_pool` / `mood_pool` | list[str] | 采样 1–2 / 1 / 1–2 项 |
| `bpm` | `Bpm{min,max,typical}` | 替代 `bpm_range`（保留 `bpm_range` 只读属性兼容） |
| `vocal_timbres` | list[str] | 本曲风适合的音色 id，未锁定时从中采样 |
| `vocal_gender_default` | str | 不变 |
| `fusion_partners` | list[str] | 融合档可选的伙伴曲风 id（2–3 个，人工挑选的兼容对） |
| `caption_skeleton` / `structure` / `lyric_rules` / `acestep` | — | 不变 |
| `examples` | list[str] | 降为兜底：检索不到示例时才用 |

旧的 `instrument_pool` 改为由 `instrument_pools` 展平得到的只读属性，避免一次性改所有调用方。

**首批 14 个曲风**（id / 中文名 / BPM typical）：

| id | 中文 | BPM | 融合伙伴 |
|---|---|---|---|
| `pop.ballad` | 流行抒情 | 72 | `rnb.soul`, `folk.acoustic` |
| `pop.city_pop` | City Pop | 108 | `jazz.lounge`, `electronic.synthwave` |
| `folk.acoustic` | 民谣 | 90 | `pop.ballad`, `cn.guofeng` |
| `rock.band` | 摇滚 | 120 | `rock.pop_punk`, `rock.anime` |
| `rock.pop_punk` | 流行朋克 | 165 | `rock.band`, `electronic.dance` |
| `rnb.soul` | R&B / Soul | 85 | `pop.ballad`, `hiphop.boom_bap` |
| `electronic.dance` | 电子舞曲 | 124 | `electronic.synthwave`, `pop.city_pop` |
| `lofi.chill` | Lo-fi | 80 | `jazz.lounge`, `hiphop.boom_bap` |
| `jazz.lounge` | 爵士 | 110 | `rnb.soul`, `lofi.chill` |
| `cn.guofeng` | 中国风 | 80 | `pop.ballad`, `electronic.dance` |
| `rock.anime` | 动漫 / J-Rock | 150 | `rock.band`, `electronic.dance` |
| `electronic.synthwave` | Synthwave | 100 | `pop.city_pop`, `rock.band` |
| `hiphop.boom_bap` | Boom Bap | 90 | `jazz.lounge`, `lofi.chill` |
| `hiphop.trap` | Trap | 140 | `electronic.dance`, `rnb.soul` |

`generic` 保留，仅作「解析失败且随机也不可用」时的最终兜底。原前端「古典」chip 下线（官方示例仅 2 条 classical，无可靠数据支撑）。

各曲风词池与互斥规则在实现计划中逐个列出；改编自 suno-prompting 的曲风（jazz、rock、ambient 等）注明出处。

### 5.2 人声音色表 — `src/vocal_timbres.py`（新）

```python
class VocalTimbre(BaseModel):
    id: str
    label: str            # 中文显示
    caption: str          # 写进 caption 的英文短语
    keywords: list[str]   # 校验:caption 至少命中一个
    genders: set[str]     # 适用性别 {"male","female"};空 = 不限
    section_tags: dict[str, str] = {}   # 段落修饰,如 {"Verse": "breathy", "Chorus": "powerful"}
```

| id | 中文 | caption 短语（示意） | 段落修饰 |
|---|---|---|---|
| `clear` | 清亮 | bright, clear vocal | — |
| `breathy` | 气声 | breathy, airy vocal | Verse: breathy |
| `raspy` | 烟嗓 / 沙哑 | raspy, gritty vocal | — |
| `deep` | 低沉磁性 | deep, warm low-register vocal | — |
| `powerful` | 高亢有力 | powerful, belting vocal | Chorus: powerful |
| `falsetto` | 假声 | delicate falsetto vocal | Chorus: falsetto |
| `soft_whisper` | 温柔耳语 | soft, whispered, intimate vocal | Verse: whispered |
| `theatrical` | 戏剧化 | theatrical, dramatic vocal | Chorus: soaring |
| `rap_rapid` | 快嘴说唱 | rapid-fire, tight rap flow | Verse: rap |
| `rap_laidback` | 慵懒说唱 | laid-back, relaxed rap flow | Verse: rap |
| `choir` | 合唱 | layered choir harmonies | Chorus: choir |

`get_timbre(id)`：未知 id 抛 `ValueError`（API 转 422）。

### 5.3 采样器 — `src/style_sampler.py`（新）

```python
class StyleDraw(BaseModel):
    preset_id: str
    instruments: list[str]
    textures: list[str]
    era: str
    moods: list[str]
    vocal_timbre: str          # timbre id
    vocal_gender: str
    bpm: int
    fusion_id: str | None = None   # 融合档的伙伴曲风
    seed: int

def sample_style(preset, *, seed, locks: Locks, creativity: str = "normal",
                 recent: list[StyleDraw] = ()) -> StyleDraw
```

- **确定性**：`random.Random(seed)` 局部实例，不碰全局随机状态；同参数必同结果。
- **乐器**：按 `poolOrder` 逐池抽 `pick_min..pick_max` 项，`rare` 池先按 `chance` 掷骰；每抽一项都过一遍 `exclusions`，冲突则跳过重抽（池耗尽就少抽）。总数上限 5。
- **锁定**（`Locks`：来自用户选择的 `moods` / `vocal_gender` / `vocal_timbre`）：锁定项不抽，直接用；音色锁定但性别不兼容时，以用户的音色为准、性别置空交给 planner。
- **防重复**：`recent`（同一用户最近 5 首的 StyleDraw，从 `spec_json` 读）中出现过的乐器、音色降权到 0.3。
- **创意度**：
  - `pure`：只用 harmonic + rhythm 池、`typical` BPM、不抽 rare；
  - `normal`（默认）：如上全流程；
  - `fusion`：在 normal 基础上从 `fusion_partners` 抽一个伙伴，再从伙伴的 color 池补 1 件乐器；planner 被要求按 Tutorial 写成"前段 A → 后段融入 B"的演进句式。
- **BPM**：`pure` 取 typical，其余在 `[typical-8, typical+8] ∩ [min,max]` 内均匀抽取。

### 5.4 示例库 — `src/data/caption_bank.json`（新）+ `scripts/build_caption_bank.py`

- 一次性脚本读取 ACE-Step `examples/text2music/*.json`，对每条 caption 做关键词打标：`genres`（按各 preset 的 `keywords`/`caption_keywords` 匹配）、`gender`（male / female / none）、`lang`；输出 JSON 入库，运行时不依赖 ACE-Step 目录。文件头记录来源与 MIT 声明。
- 检索 `pick_examples(preset_id, gender, rng, k=2..3)`：先选同曲风且同性别，不足时放宽到同曲风，再不足退回 `preset.examples`。融合档额外取伙伴曲风 1 条。
- 示例只作句式和维度参考，提示词里明确写"不要照抄"（沿用现有措辞）。

### 5.5 曲风解析 — `src/style_sampler.py::resolve_genre`

优先级：

1. `overrides.preset` 非空 → 直接用；
2. 「感觉」文本命中某 preset 的 `keywords`（命中多个时取命中数最多的，平局按注册顺序）→ 用之；
3. 「感觉」非空但没命中 → 轻量 LLM 调用：给出 14 个 `id: 中文名`，只返回一个 id；返回值不在列表 → 视为失败；
4. 以上皆无 / 失败 → 用 seed 随机挑一个，避开最近 3 首用过的曲风。

产生事件 `{"stage": "曲风识别", "ok": bool, "source": "ui|keyword|llm|random"}`。第 4 步不算降级（`ok=True, source=random`）；第 3 步 LLM 失败转第 4 步时 `ok=False, reason="llm_error"`。

### 5.6 planner — `src/planner.py`

提示词结构调整：

```
用户想要的感觉:{style}                     ← 可能为空
硬性要求(必须全部体现在 caption 中,不得替换):
- 曲风: {preset.label} ({caption_keywords 前 2 个})
- 乐器: {draw.instruments}
- 质感: {draw.textures};年代/制作: {draw.era}
- 情绪: {draw.moods}
- 人声: {gender} {timbre.caption}
- BPM: {draw.bpm}
[融合档] 编曲演进: 以 {preset} 开始,后段逐渐融入 {fusion} 的 {fusion_instrument}
禁止出现的词: {preset.avoid}
官方示例(学习句式与维度,不要照抄):
{检索到的 2–3 条}
```

输出契约不变（JSON，字段同前）。`bpm` 不再由 LLM 决定，以 `draw.bpm` 覆盖 LLM 输出；`genre` / `mood` / `instrument` 也以 draw 为准写回 spec，保证 spec 与 caption 一致。

**caption 校验** `check_caption(caption, preset, timbre) -> str | None`（返回失败原因）：
- 含 CJK → `non_english`；
- 未命中 `preset.caption_keywords` → `missing_genre`；
- 未命中 `timbre.keywords` → `missing_timbre`；
- 命中 `preset.avoid` → `conflict`。

失败时把原因写进追加提示（"上次输出缺少曲风词 xxx，请修正"）**重试 1 次**；仍失败 → `render_skeleton(draw)`（骨架用 draw 的具体要素填充，而不是池中前几项，保证降级也有多样性），事件 `ok=False, reason=<上述原因>`。

**删除** `pipeline._apply_overrides` 对 genre / mood 的事后覆盖（R1）：这两项改为在采样前作为锁定输入。`language` 覆盖保留。

### 5.7 歌词段落修饰 — `src/lyric_text.py`

`apply_structure_tags(text, structure, vocal_qualifier)` 泛化为 `apply_structure_tags(text, structure, section_tags: dict[str, str])`：

- 现有 `vocal_qualifier` 等价于 `{"Verse": qualifier}`，旧调用经适配保持行为不变；
- 合并顺序：preset 的 `{"Verse": vocal_qualifier}` → 音色的 `section_tags`（音色优先）；
- 只改**无 `-` 修饰的**标签行，例如 `[Chorus]` → `[Chorus - powerful]`；用户自己写了修饰的标签不动；
- 每个标签最多一个修饰词（Tutorial 警告不要堆叠）；
- 只动标签行，`same_text` 硬校验本来就忽略标签行，不受影响。

### 5.8 seed 与可复现 — `server/queue.py`

`payload.seed` 为空时生成 `secrets.randbelow(2**31)`，同一个 seed 同时用于采样器和 DiT，并写入 `songs.seed`。现在库里大部分歌 seed 为空、无法复现，这一项顺带修复。

### 5.9 API — `server/models.py`

`Overrides` 新增：

| 字段 | 类型 | 校验 |
|---|---|---|
| `vocal_timbre` | str = `""` | 空或已知 timbre id，否则 422 |
| `creativity` | str = `"normal"` | ∈ {`pure`,`normal`,`fusion`}，否则 422 |

`preset` 校验沿用 `get_preset`，可接受 14 个新 id。`genre` 字段保留但前端不再发送（兼容旧客户端：若有值，作为曲风识别的关键词输入）。

`spec_json` 新增 `style_draw`（StyleDraw 序列化）与 `vocal.timbre`，都有默认值，旧数据照常解析，无需迁移。

### 5.10 前端

- `AdvancedSettings.tsx`：
  - 「风格预设」+「风格 chips」合并为**曲风网格**（按 `family` 分组，单选，含「自动」）；
  - 新增「人声音色」chips（单选，含「自动」），选中后若与所选性别不兼容，给出提示但不阻止提交；
  - 新增「创意度」三段控件：纯正 / 常规 / 融合；
  - 情绪 chips 保留（多选，作为锁定项）。
- 结果卡 `SongCard.tsx`：显示风格摘要（如「City Pop · 气声女声 · 108 BPM」），从 `spec_json.style_draw` 读取并映射中文名；旧歌没有 `style_draw` 时不显示。
- 「换一种」：结果卡上的按钮，用同一份歌词和用户选项、**新 seed** 再提交一次（现有生成接口，不加新端点）。
- 中文名映射表随 API 下发（`GET /api/styles` 返回曲风与音色列表），前端不再硬编码，避免两端数据不同步。

## 6. 错误处理与可见性

沿用原则：**任何降级都显式**。

| 情形 | 行为 | 用户可见 |
|---|---|---|
| 曲风 LLM 识别失败 | 随机曲风，继续出歌 | 「降级」标记：曲风识别 |
| caption 校验失败两次 | 用 draw 渲染骨架，继续出歌 | 「降级」标记 + 原因（缺曲风词 / 缺音色词 / 冲突词） |
| 未知曲风 / 音色 / 创意度 | 422 | 表单报错 |
| 音色与性别不兼容 | 以音色为准，性别交给 planner | 前端提示，不阻止 |
| 采样池耗尽（互斥太多） | 少抽，不报错 | 无 |

`SongCard` 的 `REASON_TEXT` 增加：`missing_genre`、`missing_timbre`、`conflict`。

## 7. 测试策略（TDD）

- `test_presets.py`：14 个曲风 + generic 齐全；每个曲风的所有英文字段无 CJK；`caption_keywords` 非空；`fusion_partners` 都是已注册 id；`exclusions` 中的乐器都在池里；`vocal_timbres` 都是已知 id；`bpm.min ≤ typical ≤ max`。
- `test_vocal_timbres.py`：11 项齐全；`keywords` 能在各自 `caption` 中命中；未知 id 抛错。
- `test_style_sampler.py`：同 seed 结果相同、不同 seed 至少有一处不同（对 14 个曲风各跑 20 个 seed）；互斥对从不同时出现；锁定项原样保留；`pure` 不含 rare、BPM = typical；`fusion` 带伙伴；`recent` 降权生效（统计意义上：200 次采样中被降权乐器的出现率下降）；`resolve_genre` 四级优先级与事件 `source`。
- `test_caption_bank.py`：JSON 可加载；每个曲风至少有 1 条示例或回退到 `preset.examples`；检索结果按 seed 确定。
- `test_planner.py`：提示词包含 draw 的所有硬约束与检索示例；`check_caption` 四种失败原因；校验失败后重试一次（mock LLM 第二次返回合格）；两次失败回退骨架，骨架包含 draw 的乐器；spec 的 genre / mood / instrument / bpm 以 draw 为准。
- `test_lyric_text.py`：`section_tags` 修饰 `[Chorus]`；已有 `-` 的标签不动；旧的 `vocal_qualifier` 调用行为不变；`same_text` 仍成立。
- `test_pipeline.py`：overrides 的 genre / mood 不再事后覆盖；曲风识别事件进入 `llm_status`。
- `test_api.py`：`vocal_timbre` / `creativity` 透传与 422；`GET /api/styles` 返回结构。
- `test_queue.py`：seed 为空时生成并落库，同一个值传给采样器和 song_gen。
- 前端 `vitest`：曲风网格单选发送 id；音色 / 创意度发送；风格摘要渲染；旧歌无 `style_draw` 不报错。

## 8. 评测

脚本 `scripts/style_grid.py`：同一段歌词 × 全部 14 个曲风 × seed 1001，`normal` 档；只跑 planner + 采样（不出歌）即可算客观指标，出歌另行触发。

记录 `docs/superpowers/evals/style-grid.md`：

| 指标 | 计算 |
|---|---|
| 曲风命中率 | caption 命中 `caption_keywords` 的比例 |
| 两两 Jaccard | caption 小写分词去停用词后的词集 Jaccard 均值；同时报基线（当前代码对同样输入的结果） |
| 降级率 | `llm_status` 中 `ok=False` 的比例 |
| 盲听 | 打乱顺序后由评审写出曲风，统计正确率 |

本机出一首约 4–7 分钟，14 首约 1.5 小时，安排在空闲时段跑。

## 9. 决策记录

| 决策 | 结论 | 理由 |
|---|---|---|
| 谁来挑要素 | 采样器挑，planner 只负责写句子 | LLM 自己挑会收敛到最常见搭配（R2/R3）；采样可复现、可测 |
| 用户选择的地位 | 硬约束进提示词 + 校验 | 修 R1：事后覆盖对 caption 无效 |
| 示例来源 | 官方 200 条检索 | 与模型训练分布一致；MIT |
| 数据结构参考 | suno-prompting 角色分池 + 互斥 | 解决"整池照抄"和冲突乐器；MIT 可改编 |
| 首批曲风 | 14 个（见 §5.1） | 覆盖官方示例中数据较多的方向 + 中文常用 |
| 融合 | 只用预设伙伴对 | 自由组合易产生冲突词（Tutorial 原则 7） |
| 古典 | 下线 | 官方示例仅 2 条，缺数据 |
| seed | 服务端补全并落库 | 可复现是评测与「换一种」的前提 |
| LoRA / 参考音频 | 不做 | 先验证输入链收益；MLX 兼容性与内存待评估 |

## 10. 触及文件

后端：`src/presets.py`、`src/vocal_timbres.py`（新）、`src/style_sampler.py`（新）、`src/data/caption_bank.json`（新）、`src/planner.py`、`src/pipeline.py`、`src/lyrics.py`、`src/lyric_text.py`、`src/spec.py`、`server/models.py`、`server/routes.py`、`server/queue.py`，对应 `tests/`。
脚本：`scripts/build_caption_bank.py`（新）、`scripts/style_grid.py`（新）。
前端：`web/components/AdvancedSettings.tsx`、`GenerateForm.tsx`、`SongCard.tsx`、`web/lib/types.ts`、`web/lib/api.ts`、`web/test/`。
文档：`docs/superpowers/evals/style-grid.md`（新）。

## 11. 待确认

1. §5.1 的 14 个曲风是否合适？是否加粤语流行 / 国潮 / 儿歌？
2. §5.2 的 11 种音色是否够用？
3. 「换一种」用新 seed 重新出整首（约 4–7 分钟），还是只重新采样、先展示新 caption 让用户确认再出歌？本稿按前者写。
