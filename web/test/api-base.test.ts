import { afterEach, expect, it, vi } from "vitest"

afterEach(() => { vi.unstubAllEnvs(); vi.resetModules() })

it("production defaults to same origin and keeps external audio URLs", async () => {
  vi.stubEnv("NODE_ENV", "production")
  vi.stubEnv("NEXT_PUBLIC_API_BASE", undefined)
  vi.resetModules()
  const { API_BASE, mediaUrl } = await import("@/lib/api-base")
  expect(API_BASE).toBe("")
  expect(mediaUrl("/api/media/a.mp3")).toBe("/api/media/a.mp3")
  expect(mediaUrl("https://cdn/a.mp3")).toBe("https://cdn/a.mp3")
})

it("separate backend applies to local media as well as API calls", async () => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE", "http://localhost:8000/")
  vi.resetModules()
  const { API_BASE, mediaUrl } = await import("@/lib/api-base")
  expect(API_BASE).toBe("http://localhost:8000")
  expect(mediaUrl("/api/media/a.mp3")).toBe("http://localhost:8000/api/media/a.mp3")
})
