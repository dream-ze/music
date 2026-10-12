// APP_TARGET=apk:给 Capacitor 套壳用——页面带结尾斜杠(WebView 本地服务器不会自动补 .html),
// 并输出到独立目录,不覆盖网页版的 web/out。
const isApk = process.env.APP_TARGET === "apk"

/** @type {import('next').NextConfig} */
const nextConfig = {
  // 纯静态导出:生成 web/out 的静态 HTML/JS,任何静态托管都能直接服务。
  // 我们的页面都是客户端组件(运行时向后端 API 取数),静态壳 + 前端水合即可。
  output: "export",
  images: { unoptimized: true },
  ...(isApk ? { trailingSlash: true, distDir: "out-apk" } : {}),
}
export default nextConfig
