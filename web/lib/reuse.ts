import type { AdvValue } from "@/components/AdvancedSettings"
import type { Song } from "./types"

const KEY = "zemusic.reuse"

/** 「复用设置」带回创作页的内容。情绪是采样出来的,不带回,让新歌换一组。 */
export interface ReuseDraft {
  lyrics: string
  feeling: string
  instrumental: boolean
  adv: Partial<AdvValue>
}

export function draftFromSong(song: Song): ReuseDraft {
  const base = {
    lyrics: song.lyrics || "",
    feeling: song.feeling || "",
    instrumental: song.instrumental === 1,
  }
  let spec
  try {
    spec = JSON.parse(song.spec_json || "{}")
  } catch {
    return { ...base, adv: {} }
  }
  const draw = spec?.style_draw
  if (!draw) {
    // 老歌只有 preset_id;generic 等于没选,不带
    const pid = spec?.preset_id
    return { ...base, adv: pid && pid !== "generic" ? { preset: pid } : {} }
  }
  const instrumental = draw.vocal_timbre === "instrumental"
  return {
    ...base,
    adv: {
      preset: draw.preset_id,
      vocal_timbre: instrumental ? "" : draw.vocal_timbre,
      vocal_gender: instrumental ? "" : draw.vocal_gender || "",
      creativity: draw.fusion_id ? "fusion" : "normal",
    },
  }
}

export function saveReuse(draft: ReuseDraft): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(draft))
  } catch {
    // 隐私模式等存不进去:复用失败不影响别的功能
  }
}

/** 取出并清掉,避免刷新创作页时又被填一遍 */
export function takeReuse(): ReuseDraft | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    sessionStorage.removeItem(KEY)
    return raw ? (JSON.parse(raw) as ReuseDraft) : null
  } catch {
    return null
  }
}
