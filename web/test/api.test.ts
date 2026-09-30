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

describe("api 自定义分类", () => {
  it("listCategories 返回数组", async () => {
    vi.stubGlobal("fetch", mockFetch({ categories: [{ id: "c1", name: "民谣" }] }))
    const cats = await api.listCategories()
    expect(cats).toHaveLength(1)
    expect(cats[0].name).toBe("民谣")
  })

  it("createCategory 发 POST 带 name", async () => {
    const f = mockFetch({ id: "c1", name: "民谣" })
    vi.stubGlobal("fetch", f)
    const cat = await api.createCategory("民谣")
    expect(cat.id).toBe("c1")
    const [url, opts] = f.mock.calls[0]
    expect(String(url)).toContain("/api/categories")
    expect(opts.method).toBe("POST")
    expect(JSON.parse(opts.body)).toEqual({ name: "民谣" })
  })

  it("deleteCategory 发 DELETE", async () => {
    const f = mockFetch({ deleted: true })
    vi.stubGlobal("fetch", f)
    await api.deleteCategory("c1")
    const [url, opts] = f.mock.calls[0]
    expect(String(url)).toContain("/api/categories/c1")
    expect(opts.method).toBe("DELETE")
  })

  it("addSongToCategory 发 PUT 到 categories/{id}", async () => {
    const f = mockFetch({ category_ids: ["c1"] })
    vi.stubGlobal("fetch", f)
    const ids = await api.addSongToCategory("s1", "c1")
    expect(ids).toEqual(["c1"])
    const [url, opts] = f.mock.calls[0]
    expect(String(url)).toContain("/api/songs/s1/categories/c1")
    expect(opts.method).toBe("PUT")
  })

  it("removeSongFromCategory 发 DELETE 到 categories/{id}", async () => {
    const f = mockFetch({ category_ids: [] })
    vi.stubGlobal("fetch", f)
    const ids = await api.removeSongFromCategory("s1", "c1")
    expect(ids).toEqual([])
    const [url, opts] = f.mock.calls[0]
    expect(String(url)).toContain("/api/songs/s1/categories/c1")
    expect(opts.method).toBe("DELETE")
  })

  it("listSongs 带 category 参数", async () => {
    const f = mockFetch({ songs: [] })
    vi.stubGlobal("fetch", f)
    await api.listSongs({ category: "c1" })
    expect(String(f.mock.calls[0][0])).toContain("category=c1")
  })
})
