import { describe, it, expect, beforeEach, vi } from "vitest"
import { getPasscode, setPasscode, hasPasscode } from "@/lib/passcode"

beforeEach(() => {
  const store: Record<string, string> = {}
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => {
      store[k] = v
    },
    removeItem: (k: string) => {
      delete store[k]
    },
  })
})

describe("passcode", () => {
  it("默认无口令", () => {
    expect(getPasscode()).toBe("")
    expect(hasPasscode()).toBe(false)
  })
  it("设置后可读取", () => {
    setPasscode("sesame")
    expect(getPasscode()).toBe("sesame")
    expect(hasPasscode()).toBe(true)
  })
})
