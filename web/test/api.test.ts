import { describe, it, expect, vi, beforeEach } from "vitest"
import * as api from "@/lib/api"

function mockFetch(json: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    json: () => Promise.resolve(json),
  })
}

beforeEach(() => {
  vi.stubGlobal("localStorage", {
    getItem: () => "sesame",
    setItem: () => {},
    removeItem: () => {},
  })
})

describe("api", () => {
  it("generate 发 POST 并带口令 header", async () => {
    const f = mockFetch({ job_id: "j1" })
    vi.stubGlobal("fetch", f)
    const r = await api.generate({
      lyrics: "词",
      feeling: "女声",
      length: "full",
      seed: null,
      instrumental: false,
      overrides: {},
    })
    expect(r.job_id).toBe("j1")
    const [url, opts] = f.mock.calls[0]
    expect(String(url)).toContain("/api/generate")
    expect(opts.method).toBe("POST")
    expect(opts.headers["X-Passcode"]).toBe("sesame")
  })

  it("getJob 返回状态", async () => {
    vi.stubGlobal("fetch", mockFetch({ status: "done", song: { id: "s1" } }))
    const j = await api.getJob("j1")
    expect(j.status).toBe("done")
  })

  it("listSongs 拼接筛选参数并返回数组", async () => {
    const f = mockFetch({ songs: [{ id: "s1" }] })
    vi.stubGlobal("fetch", f)
    const songs = await api.listSongs({ favorite: true, q: "夏" })
    expect(songs).toHaveLength(1)
    expect(String(f.mock.calls[0][0])).toContain("favorite=true")
    expect(String(f.mock.calls[0][0])).toContain("q=%E5%A4%8F")
  })

  it("toggleFavorite 返回布尔", async () => {
    vi.stubGlobal("fetch", mockFetch({ favorite: true }))
    expect(await api.toggleFavorite("s1")).toBe(true)
  })

  it("请求失败抛错", async () => {
    vi.stubGlobal("fetch", mockFetch({ detail: "口令错误" }, false, 401))
    await expect(api.getJob("j1")).rejects.toThrow()
  })
})
