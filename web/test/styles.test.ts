// web/test/styles.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest"
import { styleSummary, loadStyles, resetStylesCache } from "@/lib/styles"
import { getStyles } from "@/lib/api"
import type { Styles } from "@/lib/types"

vi.mock("@/lib/api", () => ({ getStyles: vi.fn() }))

const STYLES: Styles = {
  genres: [
    { id: "pop.city_pop", label: "City Pop", family: "pop" },
    { id: "jazz.lounge", label: "爵士", family: "chill" },
  ],
  timbres: [{ id: "breathy", label: "气声" }],
  creativity: [{ id: "normal", label: "常规" }],
}

const spec = (draw: object | null) =>
  JSON.stringify({ vocal: { gender: "female" }, style_draw: draw })

const DRAW = {
  preset_id: "pop.city_pop", vocal_timbre: "breathy", vocal_gender: "female", bpm: 108,
  fusion_id: null,
}

describe("styleSummary", () => {
  it("拼出 曲风 · 音色+性别 · BPM", () => {
    expect(styleSummary(spec(DRAW), STYLES)).toBe("City Pop · 气声女声 · 108 BPM")
  })
  it("融合档显示伙伴曲风", () => {
    expect(styleSummary(spec({ ...DRAW, fusion_id: "jazz.lounge" }), STYLES)).toBe(
      "City Pop × 爵士 · 气声女声 · 108 BPM",
    )
  })
  it("没有选项列表时退回 id", () => {
    expect(styleSummary(spec({ ...DRAW, vocal_gender: "male" }), null)).toBe(
      "pop.city_pop · breathy男声 · 108 BPM",
    )
  })
  it("老歌没有 style_draw 或 JSON 坏掉返回 null", () => {
    expect(styleSummary(spec(null), STYLES)).toBeNull()
    expect(styleSummary("{bad", STYLES)).toBeNull()
    expect(styleSummary("", STYLES)).toBeNull()
  })
})

describe("loadStyles", () => {
  beforeEach(() => {
    resetStylesCache()
    vi.mocked(getStyles).mockReset()
  })
  it("只请求一次", async () => {
    vi.mocked(getStyles).mockResolvedValue(STYLES)
    await loadStyles()
    await loadStyles()
    expect(getStyles).toHaveBeenCalledTimes(1)
  })
  it("失败后清缓存,下次重试", async () => {
    vi.mocked(getStyles).mockRejectedValueOnce(new Error("x")).mockResolvedValue(STYLES)
    await expect(loadStyles()).rejects.toThrow()
    await expect(loadStyles()).resolves.toEqual(STYLES)
  })
})
