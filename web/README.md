# ze music — 前端

Next.js(App Router)+ TypeScript + Tailwind,深色霓虹风格。对接 FastAPI 后端。

## 本地开发

```bash
cd web
npm install
cp .env.local.example .env.local   # 确认 NEXT_PUBLIC_API_BASE 指向后端
npm run dev                         # http://localhost:3000
```

后端需在 `.env.local` 指定的地址运行(本地默认 `http://localhost:8000`,用仓库根的 `./run_api.sh` 启动)。首次进入需输入口令(对应后端环境变量 `APP_PASSCODE`;后端 `APP_PASSCODE` 为空时任意口令即可)。

## 测试与构建

```bash
npm run test    # Vitest(纯逻辑与关键组件)
npm run build   # 生产构建
```

## 环境变量

| 变量 | 说明 | 示例 |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | 后端 API 基址 | 本地 `http://localhost:8000`;线上 Tailscale `https://<机器>.<tailnet>.ts.net` |

## 部署到 Vercel

1. 把仓库连接到 Vercel。
2. **Root Directory** 设为 `web`(项目在子目录)。
3. 环境变量 `NEXT_PUBLIC_API_BASE` 填后端的 Tailscale 公网地址(`*.ts.net`)。
4. 部署后拿到 Vercel 域名(如 `ze-music.vercel.app`)。
5. **后端**需把该 Vercel 域名加入 `CORS_ORIGINS` 环境变量(逗号分隔),否则浏览器跨域被拦。

## 与后端的契约

调用这些接口(详见 `docs/superpowers/specs/2026-09-04-ze-music-web-app-design.md`):
`POST /api/generate`、`GET /api/jobs/{id}`、`GET /api/songs`、`POST /api/songs/{id}/favorite`、`GET /api/inspirations`。所有请求带 `X-Passcode` header(口令存于浏览器 localStorage)。
