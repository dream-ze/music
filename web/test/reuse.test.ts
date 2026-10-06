import { describe, it, expect, beforeEach } from "vitest"
import { draftFromSong, saveReuse, takeReuse } from "@/lib/reuse"
import type { Song } from "@/lib/types"

const song = (spec: object, extra: Partial<Song> = {}) =>
  ({
    id: "s1", title: "t", lyrics: "[Verse]\n词", feeling: "夜晚", instrumental: 0,
    spec_json: JSON.stringify(spec), ...extra,
  }) as Song

describe("draftFromSong", () => {
  it("带回歌词/感觉,以及曲风/音色/性别/创意度", () => {
    const d = draftFromSong(
      song({
        preset_id: "pop.city_pop", vocal: { gender: "female", timbre: "breathy" },
        style_draw: { preset_id: "pop.city_pop", vocal_timbre: "breathy",
                      vocal_gender: "female", fusion_id: "jazz.lounge" },
      }),
    )
    expect(d).toEqual({
      lyrics: "[Verse]\n词", feeling: "夜晚", instrumental: false,
      adv: { preset: "pop.city_pop", vocal_timbre: "breathy", vocal_gender: "female",
             creativity: "fusion" },
    })
  })

  it("纯音乐不带人声设置", () => {
    const d = draftFromSong(
      song({ style_draw: { preset_id: "lofi.chill", vocal_timbre: "instrumental",
                           vocal_gender: "", fusion_id: null } }, { instrumental: 1 }),
    )
    expect(d.instrumental).toBe(true)
    expect(d.adv).toEqual({ preset: "lofi.chill", vocal_timbre: "", vocal_gender: "",
                            creativity: "normal" })
  })

  it("老歌(没有 style_draw / generic / 坏 JSON)只带回歌词和感觉", () => {
    expect(draftFromSong(song({ preset_id: "generic" })).adv).toEqual({})
    expect(draftFromSong({ ...song({}), spec_json: "{bad" } as Song).adv).toEqual({})
    expect(draftFromSong(song({ preset_id: "rock.band" })).adv).toEqual({ preset: "rock.band" })
  })
})

describe("saveReuse / takeReuse", () => {
  beforeEach(() => sessionStorage.clear())
  it("取一次就清掉", () => {
    saveReuse({ lyrics: "a", feeling: "b", instrumental: false, adv: {} })
    expect(takeReuse()?.lyrics).toBe("a")
    expect(takeReuse()).toBeNull()
  })
  it("存储坏数据时返回 null", () => {
    sessionStorage.setItem("zemusic.reuse", "{bad")
    expect(takeReuse()).toBeNull()
  })
})
