# 风格网格评测（多曲风与人声音色）

## 指标

| 指标 | 计算 |
|---|---|
| 曲风命中率 | caption 命中所选曲风关键词的比例 |
| 两两 Jaccard | caption 小写分词、去停用词后的词集 Jaccard 均值（越低越多样） |
| 降级率 | `llm_status` 中 `ok=False` 的比例 |
| 盲听 | 打乱顺序后评审写出曲风，统计正确率 |

## 基线（改动前，2026-10-06，DeepSeek，commit ae294f2）

### A. 「感觉」里直接写曲风名（preset 为空，只跑 planner）

| 感觉 | planner | caption（前 120 字） |
|---|---|---|
| 流行抒情 | ok | A contemporary pop ballad led by soft piano and lush strings, with a warm, intimate female vocal that builds into a laye |
| City Pop | ok | A 1980s city pop track featuring electric piano, funky bass guitar, and glossy synthesizers, with a smooth and airy male |
| 民谣 | ok | A timeless folk track featuring fingerpicked acoustic guitar, harmonica, and double bass, with a warm, sparse production |
| 摇滚 | ok | A modern rock track featuring distorted electric guitars, driving bass and pounding drums, with a raw, powerful male voc |
| 流行朋克 | ok | A 2000s pop punk track featuring distorted electric guitars, driving bass and fast live drums, with a raw, punchy produc |
| R&B | ok | A modern contemporary R&B track featuring warm Rhodes electric piano, smooth synth pads, grooving bass guitar, and soft |
| 电子舞曲 | ok | A 2020s electronic dance track featuring pulsating synthesizers and driving bass, with a polished production and an ener |
| Lo-fi | ok | A 2020s lo-fi chillhop track featuring warm electric piano, mellow guitar, and soft drums, with a dusty, tape-saturated |
| 爵士 | ok | A mid-tempo jazz track featuring grand piano, upright bass, and a smoky saxophone, with a warm, intimate production and |
| 中国风 | ok | A serene, mid-tempo Chinese traditional folk track set in a timeless ancient era, featuring guzheng, erhu, dizi flute, a |
| 动漫 J-Rock | ok | A modern 2020s anime J-rock track featuring driving electric guitar riffs, punchy bass, live drums and bright synth laye |
| Synthwave | ok | A retro 80s synthwave track featuring analog synths and punchy drum machines, with a neon-drenched production and an eth |
| boom bap 说唱 | ok | A 90s boom bap track featuring dusty drum breaks, upright bass and soulful vinyl samples, with a gritty, rhythmic male r |
| trap 说唱 | ok | A modern trap track featuring booming 808 bass, rapid hi-hats, and dark synths, with a gritty male rap vocal delivering |

两两 Jaccard 均值：**0.189**

结论：用户把曲风写进「感觉」时，现有 planner 已能区分曲风。**这不是主要问题场景。**

### B. 「感觉」留空，只点曲风 chip（真实最常见用法；走完整 pipeline，mock 掉断行与出歌）

| chip | 命中 | caption（前 110 字） |
|---|---|---|
| pop | ✓ | A warm, mid-tempo pop ballad from the 2010s featuring soft piano and airy pads, with a gentle acoustic guitar |
| folk | ✗ | A 2000s pop ballad featuring warm piano and lush strings, with an intimate female vocal carrying the melody ov |
| rock | ✗ | A 2020s pop ballad featuring soft piano and lush strings, with a warm, atmospheric production and a breathy fe |
| r&b | ✗ | A 2000s pop ballad track featuring soft piano and airy synth pads, with a warm, intimate female vocal carrying |
| electronic | ✗ | A warm, mid-tempo pop ballad from the 2010s featuring acoustic guitar and soft piano, with a clean, intimate p |
| hip hop | ✗ | A heartfelt acoustic pop track from the 2000s era featuring warm acoustic guitar and soft strings, with a gent |
| pop | ✓ | A warm, mid-tempo pop ballad led by soft piano and subtle acoustic guitar, with airy synth pads and quiet stri |
| folk | ✗ | A contemporary pop ballad led by soft piano and acoustic guitar, with a warm, nostalgic production and an inti |
| rock | ✗ | A modern pop ballad track featuring soft piano and airy strings, with a warm, intimate production and a gentle |
| r&b | ✗ | A nostalgic 2020s indie pop track featuring warm piano and acoustic guitar, with a raw, intimate production an |
| electronic | ✗ | A warm, mid-tempo pop ballad from the 2000s featuring soft piano and airy pads, with a textured production and |
| hip hop | ✗ | A 2000s indie folk track featuring acoustic guitar, harmonica and brushed drums, with a raw analog production |
| pop | ✓ | A modern pop track featuring piano, synth pads, acoustic guitar, and strings, with a warm, airy production and |
| rock | ✗ | A warm, mid-tempo pop ballad led by soft piano and airy pads, with an intimate female vocal carrying the melod |

曲风命中：**3/14**（只有选 pop 的命中）；两两 Jaccard 均值：**0.371**

结论：证实设计 §1 的 R1 + R2 —— chip 进不了 planner，空「感觉」时 planner 照抄 generic 唯一示例，14 首几乎都是 "warm pop ballad + soft piano + airy pads + intimate vocal"。**验收以场景 B 为准**：目标命中 14/14、Jaccard < 0.25。

## 改动后

（Task 15 填写）
