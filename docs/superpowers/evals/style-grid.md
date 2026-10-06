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

## 改动后（2026-10-06，DeepSeek，Task 1–14 完成后）

脚本：`scripts/style_grid.py`（与基线场景 B 对应：「感觉」留空，曲风由界面选定）。

### seed 1001（normal 档，「感觉」留空，曲风由 UI 选定）

| 曲风 | 音色 | 乐器 | 命中 | caption(前 120 字) |
|---|---|---|---|---|
| 流行抒情 | falsetto | electric piano, soft choir, brushed drums | ✓ | A 2000s pop ballad at 70 BPM featuring electric piano, soft choir, and brushed drums, with an intimate production and a  |
| City Pop | falsetto | clean electric guitar chords, lush strings, four-on-the-floor drums | ✓ | A carefree, dreamy 80s Tokyo city pop track at 106 BPM with clean electric guitar chords, lush strings, and four-on-the- |
| 民谣 | deep | nylon-string guitar, banjo | ✓ | A 2010s indie folk song built on nylon-string guitar and banjo, with organic, raw production and a heartfelt, peaceful m |
| 摇滚 | clear | overdriven guitar riffs, string pads, driving bass guitar, punchy live drums, cowbell | ✓ | A 90s rock track driven by overdriven guitar riffs, string pads, driving bass guitar, punchy live drums, and cowbell. Th |
| 流行朋克 | clear | bright distorted guitars, driving bass guitar, fast punk drums, handclaps | ✓ | A 2000s pop punk anthem with bright distorted guitars, driving bass guitar, fast punk drums, and handclaps. It sounds ra |
| R&B / Soul | powerful | neo-soul guitar chords, synth bass, finger snaps | ✓ | A 2000s R&B soul track at 78 BPM with neo-soul guitar chords, synth bass, and finger snaps. The production is intimate a |
| 电子舞曲 | breathy | bright synth stabs, piano house chords, sidechained bass, four-on-the-floor kick, talk box | ✓ | A modern electronic dance track built on bright synth stabs, piano house chords, sidechained bass, a four-on-the-floor k |
| Lo-fi | rap_laidback | soft piano, muted trumpet, soft kick and snare | ✓ | A bedroom lo-fi chill track with soft piano, muted trumpet, and soft kick and snare. The sound is mellow and melancholic |
| 爵士 | clear | Hammond organ, clarinet, brushed drums | ✓ | A modern jazz song with Hammond organ, clarinet, and brushed drums. The live recording feels romantic and laid-back at 1 |
| 中国风 | theatrical | soft piano, string section, traditional percussion | ✓ | An ancient-inspired chinese-style pop song blending soft piano, string section, and traditional percussion. The producti |
| 动漫 / J-Rock | theatrical | bright overdriven guitar riffs, lead guitar solo, busy bass guitar, driving rock drums, glockenspiel | ✓ | A 2010s anime-style J-rock song at 148 BPM with bright overdriven guitar riffs, lead guitar solo, busy bass guitar, driv |
| Synthwave | falsetto | warm polysynth chords, arpeggiated synth bass, linn drum machine | ✓ | A modern retro synthwave track with warm polysynth chords, arpeggiated synth bass, and a Linn drum machine. The sound is |
| Boom Bap | deep | soul guitar loop, soul vocal sample, upright bass, dusty drum break, turntable scratches | ✓ | A 90s boom bap hip-hop track built on soul guitar loop, soul vocal sample, upright bass, dusty drum break, and turntable |
| Trap | raspy | bell melody, rolling hi-hats, 808 sub-bass, flute loop | ✓ | A modern trap track driven by a bell melody, rolling hi-hats, 808 sub-bass, and a flute loop. The mix is dark and modern |


曲风命中率: 14/14
降级率: 0/14
两两 Jaccard 均值: 0.121

### seed 1002（normal 档，「感觉」留空，曲风由 UI 选定）

| 曲风 | 音色 | 乐器 | 命中 | caption(前 120 字) |
|---|---|---|---|---|
| 流行抒情 | breathy | electric piano, string section, soft drums | ✓ | A 2000s pop ballad at 65 BPM featuring electric piano, string section, and soft drums, with an intimate production. A fe |
| City Pop | clear | clean electric guitar chords, funky slap bass, groovy live drums | ✓ | An 80s Tokyo city pop track with clean electric guitar chords, funky slap bass, and groovy live drums. The production is |
| 民谣 | breathy | nylon-string guitar, harmonica, light percussion | ✓ | A 2010s indie acoustic folk song built on nylon-string guitar, harmonica, and light percussion, with a raw recording and |
| 摇滚 | theatrical | overdriven guitar riffs, lead guitar solo, punchy live drums, driving bass guitar, cowbell | ✓ | A 90s rock track driven by overdriven guitar riffs, lead guitar solo, punchy live drums, driving bass guitar, and cowbel |
| 流行朋克 | raspy | bright distorted guitars, fast punk drums, driving bass guitar | ✓ | An early 2000s pop punk anthem at 158 BPM with bright distorted guitars, fast punk drums, and driving bass guitar. It so |
| R&B / Soul | powerful | neo-soul guitar chords, lush strings, laid-back drums, finger snaps, harp | ✓ | A 90s R&B soul track with neo-soul guitar chords, lush strings, laid-back drums, finger snaps, and harp. The production  |
| 电子舞曲 | falsetto | bright synth stabs, vocal chops, four-on-the-floor kick, crisp claps, talk box | ✓ | A modern electronic dance track built on bright synth stabs, vocal chops, four-on-the-floor kick, crisp claps, and talk  |
| Lo-fi | rap_laidback | soft piano, vinyl crackle, dusty boom bap drums, round bass, wind chimes | ✓ | A modern lo-fi chill track with soft piano, vinyl crackle, dusty boom bap drums, round bass, and wind chimes. The sound  |
| 爵士 | clear | Hammond organ, tenor sax, upright bass, ride cymbal, bongos | ✓ | A 50s jazz song with Hammond organ, tenor sax, upright bass, ride cymbal, and bongos. The recording feels warm, with smo |
| 中国风 | falsetto | soft piano, erhu, soft drums | ✓ | A modern Chinese-style pop ballad at 73 BPM blending soft piano, erhu, and soft drums. The production is lush, and a fem |
| 动漫 / J-Rock | raspy | bright overdriven guitar riffs, synth brass fanfare, driving rock drums, busy bass guitar, glockenspiel | ✓ | A triumphant, adventurous 2010s anime J-rock song with bright overdriven guitar riffs, synth brass fanfare, driving rock |
| Synthwave | falsetto | warm polysynth chords, bright synth lead, gated reverb drums, pulsing bass, talk box | ✓ | A nostalgic 80s synthwave track with warm polysynth chords, bright synth lead, gated reverb drums, pulsing bass, and tal |
| Boom Bap | raspy | soul guitar loop, muted trumpet stabs, dusty drum break, upright bass, turntable scratches | ✓ | A gritty 90s boom bap hip-hop track built on soul guitar loop, muted trumpet stabs, dusty drum break, upright bass and t |
| Trap | deep | bell melody, 808 sub-bass, rolling hi-hats | ✓ | A modern trap track driven by a dark bell melody, 808 sub-bass, and rolling hi-hats. The mix is hard-hitting and aggress |


曲风命中率: 14/14
降级率: 0/14
两两 Jaccard 均值: 0.124


### 对比

| 指标 | 基线 B（只点 chip） | 改后 seed 1001 | 改后 seed 1002 | 目标 |
|---|---|---|---|---|
| 曲风命中 | 3/14 | 14/14 | 14/14 | 14/14 |
| 降级率 | — | 0/14 | 0/14 | — |
| 两两 Jaccard | 0.371 | 见上 | 见上 | < 0.25 |

同曲风不同 seed 的乐器 / 音色组合不同（如民谣 1001: nylon-string guitar + banjo, deep；1002: nylon-string guitar + harmonica + light percussion, breathy）。

观察：LLM 常把人声直接写成 "a female bright, clear vocal" 这种「性别 + 音色短语」的生硬拼接（提示词里就是这么给的），可读性一般，暂不影响校验；后续可把提示词改成「音色形容词 + 性别 + vocal」。

盲听：待 Task 16 真实出歌后填写。
