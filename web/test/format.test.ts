import { describe, it, expect } from "vitest"
import { formatDuration, formatEta } from "@/lib/format"

describe("formatDuration", () => {
  it("秒转 mm:ss", () => {
    expect(formatDuration(201)).toBe("03:21")
    expect(formatDuration(5)).toBe("00:05")
    expect(formatDuration(0)).toBe("00:00")
  })
})

describe("formatEta", () => {
  it("剩余时间粗粒度显示", () => {
    expect(formatEta(30)).toBe("不到 1 分钟")
    expect(formatEta(61)).toBe("约 2 分钟")
    expect(formatEta(240)).toBe("约 4 分钟")
    expect(formatEta(null)).toBe("")
  })
})
