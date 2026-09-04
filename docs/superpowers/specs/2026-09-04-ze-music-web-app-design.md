# ze music — Web 部署设计

日期:2026-09-04
状态:已确认,待写实现计划

## 目标

把现有的本地 ACE-Step 成曲引擎(`src/`)从 Gradio 单体,改造成一个**给自己 + 少数朋友(<10 人)使用的、好看的在线音乐 app**:

- 前端:Next.js 部署在 Vercel(免费)
- 后端:FastAPI 包住现有引擎,跑在一台家里常开的机器(Mac 或 Windows)
- 内网穿透:Tailscale Funnel 把后端暴露成稳定公网 HTTPS 地址(免费,不需域名)
- 音频:WAV → MP3,存 Cloudflare R2,前端播放 R2 公网 URL
- 元数据:SQLite

现有 `src/`(planner / lyrics / song_gen / pipeline / spec / llm)**不改核心逻辑**,只在外面加 API、队列、存储与前端。

## 范围

### v1 做

- **创作页**:歌词 + 一句"感觉"(混合输入),可展开「高级设置」手动覆盖 风格/情绪/人声/语言/时长/Seed
- **作品库(画廊)页**:所有歌的卡片网格,搜索 + 筛选,点卡片播放
- **我的收藏页**:标记为收藏的歌
- **灵感示例**:一组静态预设 prompt,点一下填进创作表单
- 底部常驻波形播放器
- 异步任务 + 轮询(单 GPU 排队)
- 共享口令认证
- 深色霓虹视觉(见 `.superpowers/brainstorm/` 里确认过的 mockup)

### v1 不做(明确砍掉)

- 积分 / 定价 / 升级套餐 / 每日配额 / 支付(参考图里有,朋友自用不需要)
- 完整账号体系(注册/登录/找回)
- 下载记录页
- 调性(key)手动控件(SongSpec 暂无此字段,留到后续)
- ACE-Step 的 repaint / retake / stems / 参考音频等编辑能力(后续版本)

## 架构与数据流

```
[浏览器] ──①填歌词+感觉,点生成(带口令 header)──► [Vercel: Next.js]
                                                        │
                                          ②POST /api/generate
                                                        ▼
                                    [Tailscale Funnel  *.ts.net]
                                                        │
                                                        ▼
                                      [家里常开机器: FastAPI :8000]
                                        │ ③入队,立刻返回 job_id
                                        ▼
                                  [单 worker asyncio 队列]
                                        │ ④ run_in_executor 跑 make_song()
                                        ▼          (现有引擎, GPU 出歌 → WAV)
                                  ⑤ WAV→MP3(ffmpeg)→ 传 R2 → 写 SQLite
                                        │
[浏览器] ◄──⑥轮询 GET /api/jobs/{id} 直到 done,拿 R2 URL──┘
   │
   └─► <audio> 播放 R2 URL;画廊页 GET /api/songs 读 SQLite
```

## 组件设计

### 1. 后端 FastAPI

新增一个 `server/` 包(或根目录 `api.py`),复用现有 `src/`。

**接口:**

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/api/generate` | 校验口令 → 入队 → 返回 `{job_id}` |
| GET | `/api/jobs/{job_id}` | 查任务状态 |
| GET | `/api/songs` | 画廊列表(支持 `?q=`、`?favorite=1`、`?mine=1`、分页) |
| POST | `/api/songs/{id}/favorite` | 切换收藏 |
| GET | `/api/inspirations` | 灵感示例(静态预设) |
| GET | `/api/health` | 探活 |

**`POST /api/generate` 请求体:**

```json
{
  "lyrics": "……",
  "feeling": "女声，R&B，深夜，温柔",
  "length": "full",          // full | short
  "seed": null,               // null=随机
  "instrumental": false,
  "overrides": {              // 高级设置,全部可选;不填则由 LLM planner 推断
    "genre": ["R&B"],
    "mood": ["温柔"],
    "vocal_gender": "female",
    "language": "zh"
  }
}
```

**`GET /api/jobs/{id}` 响应:**

```json
{
  "status": "queued|running|done|error",
  "position": 2,             // queued 时的排队位置
  "song": { /* 见 songs 表, done 时填 */ },
  "error": "……"             // error 时填
}
```

**任务队列:**

- 进程内单个 `asyncio.Queue` + **一个** worker 协程(`app`启动时用 `lifespan` 拉起)。
- worker 一次只处理一个任务 = 天然保护单 GPU,不需要 Redis/Celery。
- `make_song()` 是阻塞的 GPU 调用,用 `run_in_executor` 丢到线程池,避免卡住事件循环。
- 任务状态落 SQLite `jobs` 表(不只是内存 dict),这样进程重启时未完成任务不会凭空消失(重启后标记为 error 或重新入队,实现时定)。

**流程(worker 内):**

1. `make_song(lyrics, feeling, length, seed, overrides)` → 得到 WAV 路径 + spec + structured_lyrics
2. `ffmpeg` 把 WAV 转 MP3(128k 足够)
3. 上传 MP3 到 R2(boto3,S3 兼容),得到公网 URL
4. 写 `songs` 表(标题、URL、spec、seed、时长、作者、时间)
5. 更新 `jobs` 表为 `done`,关联 `song_id`
6. 任一步失败 → `jobs` 标记 `error` + 人类可读消息

**pipeline 改造(小):**

- `make_song` 增加 `overrides` 参数:planner 产出 `SongSpec` 后,用非空的 override 字段覆盖对应字段(genre/mood/vocal.gender/language),再交给 song_gen。
- 唯一 job 目录代替固定 `outputs/song.wav`(findings.md P0-2),避免并发覆盖。虽然单 worker 已串行,但唯一目录更干净。

**LLM Key:**

- 服务器统一持有 key(环境变量 `ANTHROPIC_API_KEY` 等),朋友不用自带。
- `src/llm.py` 已支持 env fallback(`_resolve` 里),几乎零改动;前端不再暴露"选厂家/填 key"。

### 2. 存储

**Cloudflare R2:**

- 一个 bucket,MP3 存进去,配置公开访问(R2 public bucket 或绑一个 `r2.dev`/自定义域)。
- 后端用 boto3 以 S3 兼容端点上传;`R2_ACCOUNT_ID / R2_ACCESS_KEY / R2_SECRET_KEY / R2_BUCKET / R2_PUBLIC_BASE` 走环境变量。

**SQLite(家里机器本地文件):**

```
songs(
  id TEXT PK, title TEXT, lyrics TEXT, feeling TEXT,
  spec_json TEXT, structured_lyrics TEXT, seed INTEGER,
  mp3_url TEXT, duration_sec REAL, instrumental INTEGER,
  created_by TEXT, favorite INTEGER DEFAULT 0, created_at TEXT
)

jobs(
  job_id TEXT PK, status TEXT, position INTEGER,
  song_id TEXT, error TEXT, created_by TEXT, created_at TEXT
)
```

- 标题:从 feeling / 歌词首句用 LLM 或简单规则生成(实现时定,先用歌词首句兜底)。
- `created_by`:口令映射的昵称(见认证)。收藏 v1 先做全局收藏,`favorite` 布尔;若要按人收藏,后续加 `favorites(user, song_id)` 表。

### 3. 前端 Next.js(Vercel)

- App Router + Tailwind,深色霓虹主题(见确认的 mockup)。
- 视觉打磨阶段用 frontend-design 技能。
- 页面:
  - `/`(创作):歌词区 + 感觉输入 + 「高级设置」折叠 + 灵感示例侧栏 + 生成按钮 + 最近创作;点生成后轮询 job,完成后底部播放器播放。
  - `/library`(作品库):卡片网格 + 搜索 + 筛选(全部/我的收藏/我创作的)。
  - `/favorites`(我的收藏):`?favorite=1` 的 library。
  - 灵感:v1 作为创作页侧栏 + 静态数据,不单独成页(导航"灵感"可先指向创作页锚点)。
- 底部常驻 `<audio>` 播放器(全局 state,跨页不断)。
- API base:`NEXT_PUBLIC_API_BASE` = Cloudflare Tunnel 公网地址。
- 认证:输入口令存 `localStorage`,每次请求带 `X-Passcode` header。

### 4. 认证

- 共享口令(或一小张"昵称→口令"表),后端 `X-Passcode` 校验,值来自环境变量。
- 不做账号体系。昵称用于 `created_by` 显示和"我创作的"筛选。

### 5. Tailscale Funnel + 部署

- **Tailscale Funnel** 把家里机器的本地 `:8000` 暴露成稳定公网 HTTPS 地址 `https://<机器名>.<tailnet>.ts.net`,**免费、不需要自有域名**。
- 前置(admin 控制台一次性开启):MagicDNS、HTTPS Certificates、Funnel 权限(Access controls → "Add Funnel to policy")。
- 启动:`uvicorn server.app:app --port 8000` 后 `tailscale funnel --bg 8000`(后台常驻,自动映射到公网 443)。
- Funnel 只支持公网端口 443 / 8443 / 10000,命令默认走 443,本地端口随意(用 8000)。
- **平台坑**:若服务器是 **Mac**,必须用开源/CLI 版 Tailscale(`brew install tailscale` + `tailscaled`),App Store 版不支持 Funnel;**Windows** 普通客户端原生支持,更省事。
- FastAPI 开 CORS 允许 Vercel 前端域名。
- 部署脚本:一键拉起 uvicorn + funnel(可配开机自启),把打印出的 `*.ts.net` 地址填进 Vercel 的 `NEXT_PUBLIC_API_BASE`。

## 错误处理

- **LLM 规划失败**:现有逻辑静默回退安全默认。v1 至少在 `songs` 记一个"AI 规划是否生效"标记(findings.md P0-3),便于排查;是否在 UI 提示留到实现定。
- **GPU OOM / 生成失败**:`jobs.status=error` + 人类可读消息,前端轮询到 error 后展示"生成失败,请重试"。
- **机器离线**:Funnel 断 → 生成和画廊列表都不可用(SQLite 在家里机器上);但 R2 里的音频直链仍可播。这是自托管的固有取舍,v1 接受。
- **口令错误**:后端 401,前端提示重新输入。

## 测试

- **后端**:队列/任务状态机单测;各接口用 mock 掉 `make_song` / R2 上传 / ffmpeg;WAV→MP3 与 R2 上传各自单测(mock 外部)。现有 35 passed 测试保持通过。
- **前端**:轻量,关键组件(生成轮询、播放器)几个测试 + 手动走查。
- **真实 E2E**:在目标机器上真出 1 首完整中文歌,验证 生成→MP3→R2→画廊→播放 全链路(findings.md P0-5)。

## 仓库结构(建议)

```
src/            # 现有引擎,基本不动(pipeline 加 overrides)
server/         # 新:FastAPI app、队列、R2、SQLite、认证
  app.py  queue.py  storage.py  db.py  auth.py
web/            # 新:Next.js 前端
app.py          # 现有 Gradio,保留作本地调试兜底
config.py       # 加 R2 / 口令 / CORS 相关配置项
```

## 前置准备(部署前你需要有)

- Cloudflare 账号 + R2 bucket + API token(建 bucket、配公开访问)—— 仅用于存音频,不用买域名
- Tailscale 账号(免费 Personal 版),常开机器装好并登录;Mac 用开源/CLI 版
- 家里机器装:`tailscale`、`ffmpeg`、Python 依赖、ACE-Step 权重
- LLM API key(至少一家)
- Vercel 账号(连 GitHub 仓库自动部署)

## 实现顺序(依赖链)

1. **后端 API + 队列 + SQLite**(mock 存储先跑通任务流)
2. **WAV→MP3 + R2 上传**(真实存储)
3. **pipeline overrides + 真实 E2E**(家里机器出 1 首歌验证全链路)
4. **Next.js 前端**(创作页 + 作品库 + 收藏,深色霓虹打磨)
5. **认证 + CORS**
6. **Tailscale Funnel + Vercel 部署 + 一键启动脚本**

## 未决 / 后续

- 标题自动生成策略(先歌词首句兜底)
- 收藏是否按人(v1 全局,后续可加 `favorites` 表)
- 进程重启时未完成任务如何处理(标 error vs 重入队)
- ACE-Step 编辑能力(repaint/retake/stems)、调性控件 → 后续版本
