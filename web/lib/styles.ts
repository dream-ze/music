// web/lib/styles.ts
"use client"
import { useEffect, useState } from "react"
import { getStyles } from "./api"
import type { Styles } from "./types"

let cache: Promise<Styles> | null = null

/** 曲风/音色列表整个页面只拉一次;失败时清掉缓存,下次重试。 */
export function loadStyles(): Promise<Styles> {
  if (!cache) {
    // 包一层 Promise:getStyles 同步抛错(如测试里 mock 被还原)也走 reject,不炸组件
    cache = Promise.resolve()
      .then(() => getStyles())
      .catch((e) => {
        cache = null
        throw e
      })
  }
  return cache
}

/** 测试用 */
export function resetStylesCache() {
  cache = null
}

export function useStyles(): Styles | null {
  const [styles, setStyles] = useState<Styles | null>(null)
  useEffect(() => {
    let alive = true
    loadStyles()
      .then((s) => alive && setStyles(s))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [])
  return styles
}

const GENDER_LABEL: Record<string, string> = { female: "女声", male: "男声" }

/** 歌曲卡片上的风格摘要,如「City Pop · 气声女声 · 108 BPM」。老歌(无 style_draw)返回 null。 */
export function styleSummary(
  specJson: string | null | undefined,
  styles: Styles | null,
): string | null {
  if (!specJson) return null
  let draw
  try {
    draw = JSON.parse(specJson)?.style_draw
  } catch {
    return null
  }
  if (!draw || typeof draw !== "object") return null
  const name = (list: { id: string; label: string }[] | undefined, id: string) =>
    list?.find((o) => o.id === id)?.label ?? id
  const genre = name(styles?.genres, draw.preset_id)
  const fusion = draw.fusion_id ? ` × ${name(styles?.genres, draw.fusion_id)}` : ""
  const timbre =
    draw.vocal_timbre === "instrumental" ? "纯音乐" : name(styles?.timbres, draw.vocal_timbre)
  const gender = GENDER_LABEL[draw.vocal_gender] ?? ""
  return `${genre}${fusion} · ${timbre}${gender} · ${draw.bpm} BPM`
}
