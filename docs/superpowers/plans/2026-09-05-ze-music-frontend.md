# ze music 前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Next.js 做一个深色霓虹风格的音乐 app —— 创作页(混合输入)+ 作品库画廊 + 我的收藏 + 灵感示例 + 底部常驻播放器,对接已就绪的 FastAPI 后端,部署到 Vercel。

**Architecture:** Next.js(App Router)+ TypeScript + Tailwind CSS,深色霓虹主题用 CSS 变量。异步生成走"POST /api/generate → 轮询 /api/jobs/{id}"。全局底部播放器用 React Context 跨页保持。共享口令存 localStorage,每次请求带 `X-Passcode`。纯逻辑(API 客户端、口令、播放器 store)用 Vitest 做 TDD;UI 用 `next build` + 浏览器预览做验收。

**Tech Stack:** Next.js 15、React 19、TypeScript、Tailwind CSS 3、Vitest + @testing-library/react + jsdom。

**Spec:** `docs/superpowers/specs/2026-09-04-ze-music-web-app-design.md`

## Global Constraints

- 前端目录:`web/`(独立 Node 项目,与 Python 后端同仓库)。
- 深色霓虹视觉:紫蓝渐变、发光按钮、三栏创作布局、卡片画廊、底部波形播放器(见已确认的 mockup)。
- 输入混合式:主界面填歌词 + 一句感觉;「高级设置」折叠里手动覆盖 风格/情绪/人声/语言/时长/Seed。
- 不做计费/积分/套餐/账号体系。
- API 基址走 `NEXT_PUBLIC_API_BASE`(本地开发 `http://localhost:8000`,上线填 Tailscale `*.ts.net` 地址)。
- 前端不接收 LLM key(服务器统一持有)。
- 网络受限环境:`npm install` / `npm run build` 若超时,用 `dangerouslyDisableSandbox` 重试(与 git push 同理)。

## 对接的后端 API(已就绪,契约固定)

- `POST /api/generate` body `{lyrics, feeling, length, seed, instrumental, overrides:{genre[],mood[],vocal_gender,language}}` → `{job_id}`
- `GET /api/jobs/{job_id}` → `{status:"queued"|"running"|"done"|"error", position, song, error}`
- `GET /api/songs?q=&favorite=&mine=&limit=&offset=` → `{songs:[...]}`
- `POST /api/songs/{id}/favorite` → `{favorite:bool}`
- `GET /api/inspirations` → `{inspirations:[{title,feeling,lyrics}]}`
- song 对象:`{id,title,lyrics,feeling,spec_json,structured_lyrics,seed,mp3_url,duration_sec,instrumental,created_by,favorite,created_at}`

---

## 文件结构

```
web/
  package.json  next.config.mjs  tsconfig.json  tailwind.config.ts  postcss.config.mjs
  vitest.config.ts  vitest.setup.ts  .env.local.example
  app/
    layout.tsx          # 根布局:主题、顶栏、侧栏、底部播放器、口令门
    globals.css         # Tailwind + 深色霓虹 CSS 变量
    page.tsx            # 创作页
    library/page.tsx    # 作品库
    favorites/page.tsx  # 我的收藏
  components/
    Nav.tsx  Sidebar.tsx  Player.tsx  SongCard.tsx
    GenerateForm.tsx  AdvancedSettings.tsx  InspirationList.tsx  PasscodeGate.tsx
  lib/
    api.ts        # API 客户端
    types.ts      # Song / Job / GenerateInput 类型
    format.ts     # 时长格式化等纯函数
    passcode.ts   # localStorage 口令读写
    player.tsx    # 全局播放器 Context + hook
  test/
    api.test.ts  format.test.ts  passcode.test.ts  player.test.tsx  SongCard.test.tsx
```

---

## Task 1: 脚手架 + Tailwind + Vitest + 深色霓虹主题

**Files:**
- Create: `web/package.json`、`web/next.config.mjs`、`web/tsconfig.json`、`web/tailwind.config.ts`、`web/postcss.config.mjs`、`web/vitest.config.ts`、`web/vitest.setup.ts`、`web/.env.local.example`、`web/app/globals.css`、`web/app/layout.tsx`、`web/app/page.tsx`、`web/lib/format.ts`、`web/test/format.test.ts`
- Modify: `.gitignore`(加 `web/node_modules`、`web/.next`、`web/.env.local`)

**Interfaces:**
- Produces:`format.formatDuration(sec: number) => string`(如 `201` → `"03:21"`);Next 应用能 `build`;Tailwind 主题变量就绪。

- [ ] **Step 1: 建 web 项目文件(package.json 等配置)**

`web/package.json`:
```json
{
  "name": "ze-music-web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run"
  },
  "dependencies": {
    "next": "15.1.3",
    "react": "19.0.0",
    "react-dom": "19.0.0"
  },
  "devDependencies": {
    "@testing-library/react": "16.1.0",
    "@testing-library/jest-dom": "6.6.3",
    "@types/node": "22.10.2",
    "@types/react": "19.0.2",
    "@types/react-dom": "19.0.2",
    "autoprefixer": "10.4.20",
    "jsdom": "25.0.1",
    "postcss": "8.4.49",
    "tailwindcss": "3.4.17",
    "typescript": "5.7.2",
    "vitest": "2.1.8",
    "@vitejs/plugin-react": "4.3.4"
  }
}
```

`web/next.config.mjs`:
```js
/** @type {import('next').NextConfig} */
const nextConfig = {}
export default nextConfig
```

`web/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022", "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true, "skipLibCheck": true, "strict": true, "noEmit": true,
    "esModuleInterop": true, "module": "esnext", "moduleResolution": "bundler",
    "resolveJsonModule": true, "isolatedModules": true, "jsx": "preserve",
    "incremental": true, "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

`web/postcss.config.mjs`:
```js
export default { plugins: { tailwindcss: {}, autoprefixer: {} } }
```

`web/tailwind.config.ts`:
```ts
import type { Config } from "tailwindcss"
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)", panel: "var(--panel)", ink: "var(--ink)",
        muted: "var(--muted)", brand: "var(--brand)", brand2: "var(--brand2)",
        line: "var(--line)",
      },
    },
  },
  plugins: [],
} satisfies Config
```

`web/.env.local.example`:
```
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

- [ ] **Step 2: 建主题 CSS 与根布局占位**

`web/app/globals.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --bg: #0c0a16; --panel: #131024; --ink: #e9e6f5; --muted: #8f8aad;
  --brand: #b06bff; --brand2: #5c7cff; --line: rgba(255,255,255,.07);
}
html, body { background: var(--bg); color: var(--ink); }
body { margin: 0; font-family: system-ui, -apple-system, "PingFang SC", sans-serif; }
.glow-btn {
  background: linear-gradient(90deg, var(--brand), var(--brand2));
  box-shadow: 0 8px 26px rgba(140,75,255,.4);
}
```

`web/app/layout.tsx`:
```tsx
import "./globals.css"

export const metadata = { title: "ze music", description: "把歌词变成一首歌" }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>{children}</body>
    </html>
  )
}
```

`web/app/page.tsx`:
```tsx
export default function Home() {
  return <main style={{ padding: 24 }}>ze music</main>
}
```

- [ ] **Step 3: 建 Vitest 配置与第一个纯函数测试**

`web/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"
import { fileURLToPath } from "node:url"

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", setupFiles: ["./vitest.setup.ts"], globals: true },
  resolve: { alias: { "@": fileURLToPath(new URL("./", import.meta.url)) } },
})
```

`web/vitest.setup.ts`:
```ts
import "@testing-library/jest-dom"
```

`web/test/format.test.ts`:
```ts
import { describe, it, expect } from "vitest"
import { formatDuration } from "@/lib/format"

describe("formatDuration", () => {
  it("秒转 mm:ss", () => {
    expect(formatDuration(201)).toBe("03:21")
    expect(formatDuration(5)).toBe("00:05")
    expect(formatDuration(0)).toBe("00:00")
  })
})
```

- [ ] **Step 4: 安装依赖并跑测试(确认失败:formatDuration 未实现)**

Run:
```bash
cd web && npm install && npx vitest run test/format.test.ts
```
Expected: 安装成功;测试 FAIL(`formatDuration` 不存在)。若 `npm install` 网络超时,用 dangerouslyDisableSandbox 重试。

- [ ] **Step 5: 实现 lib/format.ts**

`web/lib/format.ts`:
```ts
export function formatDuration(sec: number): string {
  const s = Math.max(0, Math.floor(sec || 0))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`
}
```

- [ ] **Step 6: 跑测试 + 构建**

Run:
```bash
cd web && npx vitest run test/format.test.ts && npm run build
```
Expected: 测试 PASS;`next build` 成功。

- [ ] **Step 7: 更新 .gitignore 并提交**

根 `.gitignore` 追加:
```
web/node_modules
web/.next
web/.env.local
```
```bash
git add web .gitignore
git commit -m "feat(web): Next.js 脚手架 + Tailwind 深色霓虹主题 + Vitest"
```

---

## Task 2: 类型 + API 客户端(TDD)

**Files:**
- Create: `web/lib/types.ts`、`web/lib/api.ts`、`web/test/api.test.ts`

**Interfaces:**
- Produces:
  - `types.Song`、`types.Job`、`types.GenerateInput`
  - `api.generate(input: GenerateInput) => Promise<{job_id: string}>`
  - `api.getJob(jobId: string) => Promise<Job>`
  - `api.listSongs(params?: {q?:string;favorite?:boolean;mine?:string}) => Promise<Song[]>`
  - `api.toggleFavorite(id: string) => Promise<boolean>`
  - `api.getInspirations() => Promise<{title:string;feeling:string;lyrics:string}[]>`
  - 所有请求带 `X-Passcode` header(从 `passcode.getPasscode()` 取,Task 3 提供;本任务先用内联读取 localStorage 的小函数,Task 3 再抽出)

- [ ] **Step 1: 写失败测试(mock global fetch)**

`web/test/api.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from "vitest"
import * as api from "@/lib/api"

function mockFetch(json: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok, status, json: () => Promise.resolve(json),
  })
}

beforeEach(() => {
  vi.stubGlobal("localStorage", {
    getItem: () => "sesame", setItem: () => {}, removeItem: () => {},
  })
})

describe("api", () => {
  it("generate 发 POST 并带口令 header", async () => {
    const f = mockFetch({ job_id: "j1" })
    vi.stubGlobal("fetch", f)
    const r = await api.generate({
      lyrics: "词", feeling: "女声", length: "full", seed: null,
      instrumental: false, overrides: {},
    })
    expect(r.job_id).toBe("j1")
    const [url, opts] = f.mock.calls[0]
    expect(String(url)).toContain("/api/generate")
    expect(opts.method).toBe("POST")
    expect(opts.headers["X-Passcode"]).toBe("sesame")
  })

  it("getJob 返回状态", async () => {
    vi.stubGlobal("fetch", mockFetch({ status: "done", song: { id: "s1" } }))
    const j = await api.getJob("j1")
    expect(j.status).toBe("done")
  })

  it("listSongs 拼接筛选参数并返回数组", async () => {
    const f = mockFetch({ songs: [{ id: "s1" }] })
    vi.stubGlobal("fetch", f)
    const songs = await api.listSongs({ favorite: true, q: "夏" })
    expect(songs).toHaveLength(1)
    expect(String(f.mock.calls[0][0])).toContain("favorite=true")
    expect(String(f.mock.calls[0][0])).toContain("q=%E5%A4%8F")
  })

  it("toggleFavorite 返回布尔", async () => {
    vi.stubGlobal("fetch", mockFetch({ favorite: true }))
    expect(await api.toggleFavorite("s1")).toBe(true)
  })

  it("请求失败抛错", async () => {
    vi.stubGlobal("fetch", mockFetch({ detail: "口令错误" }, false, 401))
    await expect(api.getJob("j1")).rejects.toThrow()
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd web && npx vitest run test/api.test.ts`
Expected: FAIL(`@/lib/api` 不存在)

- [ ] **Step 3: 写类型**

`web/lib/types.ts`:
```ts
export interface Song {
  id: string; title: string; lyrics: string; feeling: string
  spec_json: string; structured_lyrics: string; seed: number | null
  mp3_url: string; duration_sec: number; instrumental: number
  created_by: string; favorite: number; created_at: string
}

export interface Job {
  status: "queued" | "running" | "done" | "error"
  position: number | null
  song: Song | null
  error: string | null
}

export interface GenerateInput {
  lyrics: string; feeling: string; length: "full" | "short"
  seed: number | null; instrumental: boolean
  overrides: {
    genre?: string[]; mood?: string[]; vocal_gender?: string; language?: string
  }
}
```

- [ ] **Step 4: 写 API 客户端**

`web/lib/api.ts`:
```ts
import type { Song, Job, GenerateInput } from "./types"

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"

function passcode(): string {
  try { return localStorage.getItem("ze_passcode") || "" } catch { return "" }
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Passcode": passcode(),
      ...(init.headers || {}),
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `请求失败 ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function generate(input: GenerateInput) {
  return req<{ job_id: string }>("/api/generate", {
    method: "POST", body: JSON.stringify(input),
  })
}

export function getJob(jobId: string) {
  return req<Job>(`/api/jobs/${jobId}`)
}

export async function listSongs(
  params: { q?: string; favorite?: boolean; mine?: string } = {}
): Promise<Song[]> {
  const qs = new URLSearchParams()
  if (params.q) qs.set("q", params.q)
  if (params.favorite) qs.set("favorite", "true")
  if (params.mine) qs.set("mine", params.mine)
  const r = await req<{ songs: Song[] }>(`/api/songs?${qs.toString()}`)
  return r.songs
}

export async function toggleFavorite(id: string): Promise<boolean> {
  const r = await req<{ favorite: boolean }>(`/api/songs/${id}/favorite`, { method: "POST" })
  return r.favorite
}

export async function getInspirations() {
  const r = await req<{ inspirations: { title: string; feeling: string; lyrics: string }[] }>(
    "/api/inspirations"
  )
  return r.inspirations
}
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd web && npx vitest run test/api.test.ts`
Expected: PASS(5 passed)

- [ ] **Step 6: 提交**

```bash
git add web/lib/types.ts web/lib/api.ts web/test/api.test.ts
git commit -m "feat(web): 类型 + API 客户端(带口令 header, TDD)"
```

---

## Task 3: 口令门(passcode)

**Files:**
- Create: `web/lib/passcode.ts`、`web/components/PasscodeGate.tsx`、`web/test/passcode.test.ts`
- Modify: `web/lib/api.ts`(改用 `passcode.getPasscode()`)

**Interfaces:**
- Consumes: 无
- Produces:
  - `passcode.getPasscode() => string`、`passcode.setPasscode(v: string) => void`、`passcode.hasPasscode() => boolean`
  - `<PasscodeGate>{children}</PasscodeGate>`:无口令时显示输入框,有则渲染 children

- [ ] **Step 1: 写失败测试**

`web/test/passcode.test.ts`:
```ts
import { describe, it, expect, beforeEach, vi } from "vitest"
import { getPasscode, setPasscode, hasPasscode } from "@/lib/passcode"

beforeEach(() => {
  const store: Record<string, string> = {}
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => { store[k] = v },
    removeItem: (k: string) => { delete store[k] },
  })
})

describe("passcode", () => {
  it("默认无口令", () => {
    expect(getPasscode()).toBe("")
    expect(hasPasscode()).toBe(false)
  })
  it("设置后可读取", () => {
    setPasscode("sesame")
    expect(getPasscode()).toBe("sesame")
    expect(hasPasscode()).toBe(true)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd web && npx vitest run test/passcode.test.ts`
Expected: FAIL(`@/lib/passcode` 不存在)

- [ ] **Step 3: 实现 lib/passcode.ts**

`web/lib/passcode.ts`:
```ts
const KEY = "ze_passcode"

export function getPasscode(): string {
  try { return localStorage.getItem(KEY) || "" } catch { return "" }
}
export function setPasscode(v: string): void {
  try { localStorage.setItem(KEY, v) } catch { /* ignore */ }
}
export function hasPasscode(): boolean {
  return getPasscode().length > 0
}
```

- [ ] **Step 4: 让 api.ts 复用 passcode**

`web/lib/api.ts` 顶部改为 `import { getPasscode } from "./passcode"`,删除内联的 `passcode()` 函数,`req` 里 `"X-Passcode": getPasscode()`。

- [ ] **Step 5: 写 PasscodeGate 组件**

`web/components/PasscodeGate.tsx`:
```tsx
"use client"
import { useState, useEffect } from "react"
import { getPasscode, setPasscode } from "@/lib/passcode"

export default function PasscodeGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false)
  const [ok, setOk] = useState(false)
  const [val, setVal] = useState("")

  useEffect(() => { setOk(getPasscode().length > 0); setReady(true) }, [])
  if (!ready) return null
  if (ok) return <>{children}</>

  return (
    <div style={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center" }}>
      <div className="bg-panel" style={{ padding: 28, borderRadius: 14, width: 320 }}>
        <h2 style={{ marginTop: 0 }}>🎵 ze music</h2>
        <p className="text-muted" style={{ fontSize: 13 }}>输入口令进入</p>
        <input
          type="password" value={val} onChange={(e) => setVal(e.target.value)}
          placeholder="口令"
          style={{ width: "100%", padding: 10, borderRadius: 8, background: "var(--bg)",
                   border: "1px solid var(--line)", color: "var(--ink)" }}
        />
        <button
          className="glow-btn" onClick={() => { setPasscode(val); setOk(val.length > 0) }}
          style={{ width: "100%", marginTop: 12, padding: 11, border: "none",
                   borderRadius: 8, color: "#fff", fontWeight: 700, cursor: "pointer" }}
        >进入</button>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: 跑测试 + 构建**

Run: `cd web && npx vitest run && npm run build`
Expected: PASS;build 成功。

- [ ] **Step 7: 提交**

```bash
git add web/lib/passcode.ts web/components/PasscodeGate.tsx web/lib/api.ts web/test/passcode.test.ts
git commit -m "feat(web): 共享口令门 + api 复用 passcode"
```

---

## Task 4: 全局播放器 Context + Player 组件

**Files:**
- Create: `web/lib/player.tsx`、`web/components/Player.tsx`、`web/test/player.test.tsx`

**Interfaces:**
- Consumes: `types.Song`、`format.formatDuration`
- Produces:
  - `<PlayerProvider>`、`usePlayer() => {current: Song|null; play(song: Song): void}`
  - `<Player/>`:底部常驻条,读 `usePlayer()`,用 `<audio>` 播 `current.mp3_url`

- [ ] **Step 1: 写失败测试(store 行为)**

`web/test/player.test.tsx`:
```tsx
import { describe, it, expect } from "vitest"
import { render, screen, act } from "@testing-library/react"
import { PlayerProvider, usePlayer } from "@/lib/player"
import type { Song } from "@/lib/types"

function Probe() {
  const { current, play } = usePlayer()
  return (
    <div>
      <span data-testid="cur">{current?.title ?? "无"}</span>
      <button onClick={() => play({ id: "s1", title: "夏夜" } as Song)}>play</button>
    </div>
  )
}

describe("player store", () => {
  it("play 后 current 更新", () => {
    render(<PlayerProvider><Probe /></PlayerProvider>)
    expect(screen.getByTestId("cur").textContent).toBe("无")
    act(() => { screen.getByText("play").click() })
    expect(screen.getByTestId("cur").textContent).toBe("夏夜")
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd web && npx vitest run test/player.test.tsx`
Expected: FAIL(`@/lib/player` 不存在)

- [ ] **Step 3: 实现 lib/player.tsx**

`web/lib/player.tsx`:
```tsx
"use client"
import { createContext, useContext, useState } from "react"
import type { Song } from "./types"

interface PlayerCtx { current: Song | null; play: (song: Song) => void }
const Ctx = createContext<PlayerCtx>({ current: null, play: () => {} })

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const [current, setCurrent] = useState<Song | null>(null)
  return <Ctx.Provider value={{ current, play: setCurrent }}>{children}</Ctx.Provider>
}

export function usePlayer() { return useContext(Ctx) }
```

- [ ] **Step 4: 实现 Player 组件**

`web/components/Player.tsx`:
```tsx
"use client"
import { usePlayer } from "@/lib/player"
import { formatDuration } from "@/lib/format"

export default function Player() {
  const { current } = usePlayer()
  if (!current) return null
  return (
    <div style={{ position: "fixed", left: 0, right: 0, bottom: 0, display: "flex",
      alignItems: "center", gap: 16, padding: "12px 22px", background: "#0e0b1c",
      borderTop: "1px solid var(--line)" }}>
      <div style={{ width: 34, height: 34, borderRadius: 7,
        background: "linear-gradient(135deg,#7b4bff,#4b7cff)" }} />
      <div style={{ minWidth: 120 }}>
        <div style={{ fontSize: 13 }}>{current.title}</div>
        <div className="text-muted" style={{ fontSize: 11 }}>
          {formatDuration(current.duration_sec)}
        </div>
      </div>
      <audio controls autoPlay src={current.mp3_url} style={{ flex: 1, height: 34 }} />
    </div>
  )
}
```

- [ ] **Step 5: 跑测试 + 构建**

Run: `cd web && npx vitest run test/player.test.tsx && npm run build`
Expected: PASS;build 成功。

- [ ] **Step 6: 提交**

```bash
git add web/lib/player.tsx web/components/Player.tsx web/test/player.test.tsx
git commit -m "feat(web): 全局播放器 Context + 底部常驻 Player"
```

---

## Task 5: 布局外壳(顶栏 + 侧栏 + Provider 组装)

**Files:**
- Create: `web/components/Nav.tsx`、`web/components/Sidebar.tsx`
- Modify: `web/app/layout.tsx`

**Interfaces:**
- Consumes: `PlayerProvider`、`Player`、`PasscodeGate`
- Produces: 全站外壳 —— 顶栏(logo + 创作/作品库/我的收藏/灵感 + 主题占位 + 头像)、左侧栏、底部 Player;所有页面被 `PasscodeGate` + `PlayerProvider` 包裹

- [ ] **Step 1: 写 Nav 与 Sidebar(纯展示,用 next/link)**

`web/components/Nav.tsx`:
```tsx
import Link from "next/link"

const items = [
  { href: "/", label: "创作" },
  { href: "/library", label: "作品库" },
  { href: "/favorites", label: "我的收藏" },
]

export default function Nav() {
  return (
    <header style={{ display: "flex", alignItems: "center", gap: 26,
      padding: "14px 22px", borderBottom: "1px solid var(--line)", background: "#0e0b1c" }}>
      <div style={{ fontWeight: 800, fontSize: 16 }}>🎵 <span
        style={{ background: "linear-gradient(90deg,#b06bff,#5c7cff)",
          WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
        ze music</span></div>
      <nav style={{ display: "flex", gap: 20 }}>
        {items.map((it) => (
          <Link key={it.href} href={it.href} className="text-muted"
            style={{ textDecoration: "none" }}>{it.label}</Link>
        ))}
      </nav>
      <div style={{ marginLeft: "auto", width: 30, height: 30, borderRadius: "50%",
        background: "linear-gradient(135deg,#b06bff,#5c7cff)" }} />
    </header>
  )
}
```

`web/components/Sidebar.tsx`:
```tsx
import Link from "next/link"

const items = [
  { href: "/", label: "✦ 创作" },
  { href: "/library", label: "▤ 作品库" },
  { href: "/favorites", label: "♡ 我的收藏" },
]

export default function Sidebar() {
  return (
    <aside style={{ width: 170, padding: "18px 12px",
      borderRight: "1px solid var(--line)", background: "#0b0817" }}>
      {items.map((it) => (
        <Link key={it.href} href={it.href} className="text-muted"
          style={{ display: "block", padding: "10px 12px", borderRadius: 9,
            textDecoration: "none", marginBottom: 4 }}>{it.label}</Link>
      ))}
    </aside>
  )
}
```

- [ ] **Step 2: 组装 layout.tsx**

`web/app/layout.tsx`:
```tsx
import "./globals.css"
import Nav from "@/components/Nav"
import Sidebar from "@/components/Sidebar"
import Player from "@/components/Player"
import PasscodeGate from "@/components/PasscodeGate"
import { PlayerProvider } from "@/lib/player"

export const metadata = { title: "ze music", description: "把歌词变成一首歌" }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>
        <PasscodeGate>
          <PlayerProvider>
            <Nav />
            <div style={{ display: "flex", minHeight: "calc(100vh - 59px)" }}>
              <Sidebar />
              <main style={{ flex: 1, padding: "22px 24px", paddingBottom: 90 }}>
                {children}
              </main>
            </div>
            <Player />
          </PlayerProvider>
        </PasscodeGate>
      </body>
    </html>
  )
}
```

- [ ] **Step 3: 构建验证**

Run: `cd web && npm run build`
Expected: build 成功(三个路由 `/`、`/library`、`/favorites` 中 library/favorites 尚未建,先只保证 `/` 通过 —— 若报缺页,继续 Task 6/7 再整体 build)。

> 注:library/favorites 页面在 Task 7 建。本步骤只验证 layout 外壳与 `/` 能编译。若 `next build` 因缺页失败,改跑 `npm run dev` 手动确认首页外壳渲染,Task 7 后再做整体 build。

- [ ] **Step 4: 提交**

```bash
git add web/components/Nav.tsx web/components/Sidebar.tsx web/app/layout.tsx
git commit -m "feat(web): 布局外壳(顶栏+侧栏+Provider 组装)"
```

---

## Task 6: 创作页(GenerateForm + 高级设置 + 灵感 + 轮询生成)

**Files:**
- Create: `web/components/GenerateForm.tsx`、`web/components/AdvancedSettings.tsx`、`web/components/InspirationList.tsx`
- Modify: `web/app/page.tsx`

**Interfaces:**
- Consumes: `api.generate/getJob/getInspirations`、`usePlayer`、`types.GenerateInput`
- Produces: 创作页 —— 歌词框、感觉输入、高级设置(风格/情绪/人声/语言/时长/Seed)、灵感示例(点击填表)、生成按钮(POST→轮询→完成后 `play`)

- [ ] **Step 1: 写高级设置组件(受控)**

`web/components/AdvancedSettings.tsx`:
```tsx
"use client"
import type { GenerateInput } from "@/lib/types"

const GENRES = ["流行", "民谣", "摇滚", "R&B", "电子", "古典"]
const MOODS = ["温柔", "悲伤", "治愈", "浪漫", "欢乐"]

export default function AdvancedSettings({
  value, onChange,
}: {
  value: GenerateInput["overrides"] & { length: string; seed: string }
  onChange: (patch: Partial<typeof value>) => void
}) {
  const chip = (on: boolean) =>
    ({ padding: "6px 12px", borderRadius: 8, cursor: "pointer", fontSize: 12,
       border: on ? "1px solid var(--brand)" : "1px solid var(--line)",
       background: on ? "rgba(176,107,255,.16)" : "rgba(255,255,255,.05)",
       color: on ? "#fff" : "var(--muted)" } as const)
  const toggle = (arr: string[] | undefined, v: string) =>
    (arr || []).includes(v) ? (arr || []).filter((x) => x !== v) : [...(arr || []), v]

  return (
    <div>
      <p className="text-muted" style={{ fontSize: 12 }}>风格</p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 12 }}>
        {GENRES.map((g) => (
          <span key={g} style={chip((value.genre || []).includes(g))}
            onClick={() => onChange({ genre: toggle(value.genre, g) })}>{g}</span>
        ))}
      </div>
      <p className="text-muted" style={{ fontSize: 12 }}>情绪</p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 12 }}>
        {MOODS.map((m) => (
          <span key={m} style={chip((value.mood || []).includes(m))}
            onClick={() => onChange({ mood: toggle(value.mood, m) })}>{m}</span>
        ))}
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        <select value={value.vocal_gender || ""}
          onChange={(e) => onChange({ vocal_gender: e.target.value })}>
          <option value="">人声(自动)</option>
          <option value="female">女声</option>
          <option value="male">男声</option>
        </select>
        <select value={value.length}
          onChange={(e) => onChange({ length: e.target.value })}>
          <option value="full">完整</option>
          <option value="short">短版 Demo</option>
        </select>
        <input placeholder="Seed(随机)" value={value.seed}
          onChange={(e) => onChange({ seed: e.target.value })}
          style={{ width: 90 }} />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 写灵感组件**

`web/components/InspirationList.tsx`:
```tsx
"use client"
import { useEffect, useState } from "react"
import { getInspirations } from "@/lib/api"

export default function InspirationList({
  onPick,
}: { onPick: (lyrics: string, feeling: string) => void }) {
  const [items, setItems] = useState<{ title: string; feeling: string; lyrics: string }[]>([])
  useEffect(() => { getInspirations().then(setItems).catch(() => setItems([])) }, [])
  return (
    <div className="bg-panel" style={{ padding: 16, borderRadius: 14 }}>
      <h4 style={{ marginTop: 0, fontSize: 14 }}>灵感示例</h4>
      {items.map((it) => (
        <div key={it.title} onClick={() => onPick(it.lyrics, it.feeling)}
          style={{ padding: "9px 0", borderBottom: "1px solid var(--line)", cursor: "pointer" }}>
          <div style={{ fontSize: 12.5 }}>{it.title}</div>
          <div className="text-muted" style={{ fontSize: 10.5 }}>{it.feeling}</div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: 写 GenerateForm(核心:提交 + 轮询)**

`web/components/GenerateForm.tsx`:
```tsx
"use client"
import { useState } from "react"
import { generate, getJob } from "@/lib/api"
import { usePlayer } from "@/lib/player"
import AdvancedSettings from "./AdvancedSettings"
import InspirationList from "./InspirationList"
import type { GenerateInput } from "@/lib/types"

type Status = "idle" | "queued" | "running" | "error"

export default function GenerateForm() {
  const { play } = usePlayer()
  const [lyrics, setLyrics] = useState("")
  const [feeling, setFeeling] = useState("")
  const [adv, setAdv] = useState({
    genre: [] as string[], mood: [] as string[], vocal_gender: "",
    language: "", length: "full", seed: "",
  })
  const [status, setStatus] = useState<Status>("idle")
  const [msg, setMsg] = useState("")

  async function poll(jobId: string) {
    for (;;) {
      const job = await getJob(jobId)
      if (job.status === "done" && job.song) { play(job.song); setStatus("idle"); return }
      if (job.status === "error") { setStatus("error"); setMsg(job.error || "生成失败"); return }
      setStatus(job.status)
      setMsg(job.status === "queued" ? `排队中(第 ${job.position} 位)` : "生成中…")
      await new Promise((r) => setTimeout(r, 2500))
    }
  }

  async function onSubmit() {
    setStatus("queued"); setMsg("提交中…")
    const input: GenerateInput = {
      lyrics, feeling, length: adv.length as "full" | "short",
      seed: adv.seed ? Number(adv.seed) : null, instrumental: false,
      overrides: {
        genre: adv.genre, mood: adv.mood,
        vocal_gender: adv.vocal_gender, language: adv.language,
      },
    }
    try {
      const { job_id } = await generate(input)
      await poll(job_id)
    } catch (e) {
      setStatus("error"); setMsg(e instanceof Error ? e.message : "提交失败")
    }
  }

  const busy = status === "queued" || status === "running"
  return (
    <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
      <div className="bg-panel" style={{ flex: 1.3, padding: 16, borderRadius: 14 }}>
        <h4 style={{ marginTop: 0, fontSize: 14 }}>歌词</h4>
        <textarea value={lyrics} onChange={(e) => setLyrics(e.target.value)}
          placeholder="[Verse]\n我曾走过那条街……" rows={10}
          style={{ width: "100%", background: "var(--bg)", color: "var(--ink)",
            border: "1px solid var(--line)", borderRadius: 10, padding: 12 }} />
      </div>
      <div className="bg-panel" style={{ flex: 1.1, padding: 16, borderRadius: 14 }}>
        <h4 style={{ marginTop: 0, fontSize: 14 }}>想要什么感觉</h4>
        <input value={feeling} onChange={(e) => setFeeling(e.target.value)}
          placeholder="女声，R&B，深夜，温柔"
          style={{ width: "100%", background: "var(--bg)", color: "var(--ink)",
            border: "1px solid var(--brand)", borderRadius: 10, padding: 10, marginBottom: 14 }} />
        <AdvancedSettings value={adv}
          onChange={(patch) => setAdv((s) => ({ ...s, ...patch }))} />
        <button className="glow-btn" onClick={onSubmit} disabled={busy}
          style={{ width: "100%", marginTop: 16, padding: 14, border: "none",
            borderRadius: 12, color: "#fff", fontWeight: 800, fontSize: 15,
            cursor: busy ? "not-allowed" : "pointer", opacity: busy ? 0.7 : 1 }}>
          {busy ? msg : "✦ 生成我的歌曲"}
        </button>
        {status === "error" && (
          <p style={{ color: "#ff7a8a", fontSize: 12, marginTop: 8 }}>{msg}</p>
        )}
      </div>
      <div style={{ flex: 0.85 }}>
        <InspirationList onPick={(l, f) => { setLyrics(l); setFeeling(f) }} />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: 组装创作页**

`web/app/page.tsx`:
```tsx
import GenerateForm from "@/components/GenerateForm"

export default function Home() {
  return (
    <div>
      <h1 style={{ fontSize: 26, fontWeight: 800, margin: "0 0 4px" }}>
        用 <span style={{ background: "linear-gradient(90deg,#c07bff,#6c8cff)",
          WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
          AI</span> 创作你的音乐
      </h1>
      <p className="text-muted" style={{ margin: "0 0 18px" }}>
        输入歌词,再用一句话说说你想要的感觉,剩下的交给 AI
      </p>
      <GenerateForm />
    </div>
  )
}
```

- [ ] **Step 5: 构建验证**

Run: `cd web && npm run build`
Expected: `/` 编译成功(library/favorites 仍缺,Task 7 补;若整体 build 因缺页失败,用 `npm run dev` 手动确认创作页渲染)。

- [ ] **Step 6: 提交**

```bash
git add web/components/GenerateForm.tsx web/components/AdvancedSettings.tsx web/components/InspirationList.tsx web/app/page.tsx
git commit -m "feat(web): 创作页(混合输入 + 高级设置 + 灵感 + 轮询生成)"
```

---

## Task 7: 作品库 + 我的收藏(SongCard + 列表 + 搜索/筛选)

**Files:**
- Create: `web/components/SongCard.tsx`、`web/app/library/page.tsx`、`web/app/favorites/page.tsx`、`web/test/SongCard.test.tsx`

**Interfaces:**
- Consumes: `api.listSongs/toggleFavorite`、`usePlayer`、`format.formatDuration`、`types.Song`
- Produces: `<SongCard song onPlay />`;作品库页(搜索 + 全部/我的收藏/我创作的 tab);收藏页(favorite=1)

- [ ] **Step 1: 写 SongCard 测试**

`web/test/SongCard.test.tsx`:
```tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import SongCard from "@/components/SongCard"
import type { Song } from "@/lib/types"

const song = {
  id: "s1", title: "夏夜的微风", feeling: "流行 温柔 女声", duration_sec: 201,
  mp3_url: "https://r2/s1.mp3", created_by: "ze", favorite: 0,
} as Song

describe("SongCard", () => {
  it("显示标题与时长,点击触发播放", () => {
    const onPlay = vi.fn()
    render(<SongCard song={song} onPlay={onPlay} />)
    expect(screen.getByText("夏夜的微风")).toBeInTheDocument()
    expect(screen.getByText("03:21")).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText("播放"))
    expect(onPlay).toHaveBeenCalledWith(song)
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd web && npx vitest run test/SongCard.test.tsx`
Expected: FAIL(`@/components/SongCard` 不存在)

- [ ] **Step 3: 写 SongCard**

`web/components/SongCard.tsx`:
```tsx
"use client"
import { useState } from "react"
import { toggleFavorite } from "@/lib/api"
import { formatDuration } from "@/lib/format"
import type { Song } from "@/lib/types"

export default function SongCard({ song, onPlay }: { song: Song; onPlay: (s: Song) => void }) {
  const [fav, setFav] = useState(song.favorite === 1)
  return (
    <div className="bg-panel" style={{ borderRadius: 12, overflow: "hidden",
      border: "1px solid var(--line)" }}>
      <div style={{ height: 120, position: "relative",
        background: "linear-gradient(135deg,#7b4bff,#4b7cff)" }}>
        <button aria-label="收藏"
          onClick={() => toggleFavorite(song.id).then(setFav).catch(() => {})}
          style={{ position: "absolute", top: 9, right: 9, border: "none",
            width: 24, height: 24, borderRadius: "50%", cursor: "pointer",
            background: "rgba(0,0,0,.35)", color: fav ? "#ff7ac0" : "#fff" }}>
          {fav ? "♥" : "♡"}
        </button>
        <button aria-label="播放" onClick={() => onPlay(song)}
          style={{ position: "absolute", bottom: 10, right: 10, border: "none",
            width: 34, height: 34, borderRadius: "50%", cursor: "pointer",
            background: "rgba(255,255,255,.92)", color: "#3a1a6b" }}>▶</button>
      </div>
      <div style={{ padding: "11px 12px" }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 5 }}>{song.title}</div>
        <div className="text-muted" style={{ fontSize: 10.5, marginBottom: 7 }}>{song.feeling}</div>
        <div style={{ display: "flex", justifyContent: "space-between",
          color: "var(--muted)", fontSize: 10.5 }}>
          <span>@{song.created_by}</span><span>{formatDuration(song.duration_sec)}</span>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd web && npx vitest run test/SongCard.test.tsx`
Expected: PASS

- [ ] **Step 5: 写作品库页(可复用的列表组件内联)**

`web/app/library/page.tsx`:
```tsx
"use client"
import { useEffect, useState } from "react"
import { listSongs } from "@/lib/api"
import SongCard from "@/components/SongCard"
import { usePlayer } from "@/lib/player"
import type { Song } from "@/lib/types"

export default function Library() {
  const { play } = usePlayer()
  const [songs, setSongs] = useState<Song[]>([])
  const [q, setQ] = useState("")
  const [tab, setTab] = useState<"all" | "fav">("all")

  useEffect(() => {
    listSongs({ q, favorite: tab === "fav" }).then(setSongs).catch(() => setSongs([]))
  }, [q, tab])

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 800, margin: "0 0 4px" }}>作品库</h1>
      <p className="text-muted" style={{ margin: "0 0 18px" }}>大家用 AI 创作的所有歌曲</p>
      <div style={{ display: "flex", gap: 12, marginBottom: 18 }}>
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="🔍 搜索歌名、风格、歌词"
          style={{ flex: 1, background: "var(--panel)", color: "var(--ink)",
            border: "1px solid var(--line)", borderRadius: 9, padding: "9px 13px" }} />
        <button onClick={() => setTab("all")}
          style={{ padding: "8px 14px", borderRadius: 8, border: "none", cursor: "pointer",
            background: tab === "all" ? "rgba(176,107,255,.16)" : "rgba(255,255,255,.05)",
            color: tab === "all" ? "#fff" : "var(--muted)" }}>全部</button>
        <button onClick={() => setTab("fav")}
          style={{ padding: "8px 14px", borderRadius: 8, border: "none", cursor: "pointer",
            background: tab === "fav" ? "rgba(176,107,255,.16)" : "rgba(255,255,255,.05)",
            color: tab === "fav" ? "#fff" : "var(--muted)" }}>我的收藏</button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14 }}>
        {songs.map((s) => <SongCard key={s.id} song={s} onPlay={play} />)}
      </div>
      {songs.length === 0 && <p className="text-muted">还没有歌曲</p>}
    </div>
  )
}
```

`web/app/favorites/page.tsx`:
```tsx
"use client"
import { useEffect, useState } from "react"
import { listSongs } from "@/lib/api"
import SongCard from "@/components/SongCard"
import { usePlayer } from "@/lib/player"
import type { Song } from "@/lib/types"

export default function Favorites() {
  const { play } = usePlayer()
  const [songs, setSongs] = useState<Song[]>([])
  useEffect(() => { listSongs({ favorite: true }).then(setSongs).catch(() => setSongs([])) }, [])
  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 800, margin: "0 0 18px" }}>我的收藏</h1>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14 }}>
        {songs.map((s) => <SongCard key={s.id} song={s} onPlay={play} />)}
      </div>
      {songs.length === 0 && <p className="text-muted">还没有收藏</p>}
    </div>
  )
}
```

- [ ] **Step 6: 整体构建 + 全测试**

Run: `cd web && npx vitest run && npm run build`
Expected: 全部 PASS;`next build` 三个路由都成功。

- [ ] **Step 7: 提交**

```bash
git add web/components/SongCard.tsx web/app/library/page.tsx web/app/favorites/page.tsx web/test/SongCard.test.tsx
git commit -m "feat(web): 作品库 + 我的收藏(SongCard + 搜索/筛选)"
```

---

## Task 8: 视觉打磨 + 本地联调 + 部署准备

**Files:**
- Modify: 各组件样式(打磨)
- Create: `web/README.md`(本地联调 + Vercel 部署说明)

**Interfaces:** 无新代码接口;交付可部署的前端与一次本地全链路联调。

- [ ] **Step 1: 视觉打磨**

用 frontend-design 技能过一遍:间距、发光强度、hover 态、响应式(移动端单列)、空状态、加载态。对照已确认 mockup 调整,不改数据流。改完 `npm run build` 必须仍通过。

- [ ] **Step 2: 本地全链路联调**

前置:后端在 `http://localhost:8000` 起着(`./run_api.sh`,`APP_PASSCODE` 设一个值),R2/LLM/GPU 配好(或用后端 mock)。
```bash
cd web && cp .env.local.example .env.local   # 确认指向 localhost:8000
npm run dev
```
在浏览器:输入口令 → 创作页填歌词+感觉 → 生成 → 轮询到 done → 底部播放器出声 → 作品库看到新歌 → 点红心收藏 → 收藏页可见。

- [ ] **Step 3: 写 README(部署说明)**

`web/README.md`:包含本地开发(`npm install`/`npm run dev`)、环境变量(`NEXT_PUBLIC_API_BASE`)、Vercel 部署步骤(连 GitHub 仓库、设 Root Directory 为 `web`、设环境变量为 Tailscale `*.ts.net` 地址)、以及后端需把该 Vercel 域名加入 `CORS_ORIGINS`。

- [ ] **Step 4: 提交**

```bash
git add web
git commit -m "feat(web): 视觉打磨 + 部署说明"
```

- [ ] **Step 5: 部署(手动,需你的账号)**

Vercel 连接仓库、Root Directory=`web`、环境变量 `NEXT_PUBLIC_API_BASE`=Tailscale 地址;后端 `CORS_ORIGINS` 加 Vercel 域名。属手动验收,不进 CI。

---

## Self-Review

**Spec coverage:**
- 创作页混合输入(歌词+感觉+高级设置)→ Task 6 ✅
- 作品库画廊 + 搜索/筛选 → Task 7 ✅
- 我的收藏 → Task 7(favorites 页 + SongCard 红心)✅
- 灵感示例 → Task 6(InspirationList)✅
- 底部常驻波形播放器 → Task 4(Player;波形为视觉元素,MVP 用原生 audio,打磨阶段可加波形)⚠️ 记为打磨项
- 异步轮询 → Task 6(poll)✅
- 深色霓虹视觉 → Task 1 主题 + 各组件 + Task 8 打磨 ✅
- 共享口令 → Task 3 ✅
- API 基址 env → Task 1/.env + Task 2 ✅
- 不接收 LLM key → GenerateForm 无 key 字段 ✅
- Vercel 部署 → Task 8 ✅

**Placeholder scan:** 无 TBD;每个 code step 均含完整代码。Task 8 打磨/部署为手动步骤(依赖设计判断与用户账号),已说明具体动作。✅

**Type consistency:** `GenerateInput`、`Song`、`Job` 在 api/表单/卡片间一致;`usePlayer().play(song)`、`listSongs(params)`、`toggleFavorite(id)=>boolean`、`formatDuration(sec)` 全程一致。✅

**已知取舍:**
- 播放器"波形"MVP 先用原生 `<audio>` 控件,波形动画留到打磨(Task 8)。
- 收藏是全局的(与后端一致),非按人。
- 灵感为创作页侧栏,不单独成页(导航"灵感"可后续加锚点/页面)。
