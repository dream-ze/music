import { describe, it, expect } from "vitest"
import { formatDuration } from "@/lib/format"

describe("formatDuration", () => {
  it("秒转 mm:ss", () => {
    expect(formatDuration(201)).toBe("03:21")
    expect(formatDuration(5)).toBe("00:05")
    expect(formatDuration(0)).toBe("00:00")
  })
})
