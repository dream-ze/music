/** @type {import('next').NextConfig} */
const nextConfig = {
  // 纯静态导出:生成 web/out 的静态 HTML/JS,任何静态托管都能直接服务。
  // 我们的页面都是客户端组件(运行时向后端 API 取数),静态壳 + 前端水合即可。
  output: "export",
  images: { unoptimized: true },
}
export default nextConfig
