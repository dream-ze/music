export function formatDuration(sec: number): string {
  const s = Math.max(0, Math.floor(sec || 0))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`
}

/** 剩余时间粗粒度显示(出歌要好几分钟,精确到秒没有意义) */
export function formatEta(sec: number | null | undefined): string {
  if (sec == null) return ""
  if (sec < 60) return "不到 1 分钟"
  return `约 ${Math.ceil(sec / 60)} 分钟`
}
