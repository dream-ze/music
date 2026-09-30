import { getPasscode } from "./passcode"

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"

/**
 * 把一首歌的 mp3 存到本地,参考网易云的下载体验。
 *
 * mp3 实际存在 R2,但那个桶没开 CORS,浏览器里直接 fetch R2 的公开地址
 * 会被挡掉(能用 <audio> 播放,是因为媒体标签加载不受 CORS 限制,但 JS
 * fetch 读字节数据要受限)。所以走后端 /api/songs/{id}/download 转一手——
 * 我们自己的接口本来就对前端开着 CORS,顺便还能把 Content-Disposition
 * 设成强制下载,文件名也用歌名而不是一串 uuid(具体名字后端算好从
 * 响应头里带回来)。
 *
 * 手机上(尤其 iOS Safari)网页没法直接把文件写进"文件"App,
 * 唯一贴近原生下载体验的路径是系统分享面板——支持文件分享时优先走这条,
 * 用户能直接选"存储到文件"/"存储到照片";不支持就退回浏览器下载
 * (存到"下载"文件夹,这条在电脑和安卓上是主路径)。
 */
export async function downloadSong(songId: string, title: string): Promise<void> {
  const res = await fetch(`${BASE}/api/songs/${songId}/download`, {
    headers: { "X-Passcode": getPasscode() },
  })
  if (!res.ok) throw new Error(`下载失败 ${res.status}`)
  const blob = await res.blob()

  // 后端按 RFC 5987 把中文文件名编码进了 filename*;取不到就退回用标题现算一个
  const disposition = res.headers.get("Content-Disposition") || ""
  const starMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  const plainMatch = disposition.match(/filename="?([^";]+)"?/i)
  const filename = starMatch
    ? decodeURIComponent(starMatch[1])
    : plainMatch?.[1] || `${(title || "未命名").trim().replace(/[\\/:*?"<>|]/g, "_")}.mp3`

  const file = new File([blob], filename, { type: "audio/mpeg" })

  const nav = navigator as Navigator & {
    canShare?: (data: { files: File[] }) => boolean
    share?: (data: { files: File[]; title?: string }) => Promise<void>
  }
  if (nav.share && nav.canShare?.({ files: [file] })) {
    try {
      await nav.share({ files: [file], title: filename })
      return
    } catch {
      // 用户在分享面板里取消了,或者这台设备其实不支持文件分享——都退回普通下载
    }
  }

  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = blobUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
}
