import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { downloadSong } from "@/lib/download"

function fakeResponse(
  ok: boolean,
  opts: { blob?: Blob; disposition?: string } = {}
) {
  const blob = opts.blob ?? new Blob(["x"], { type: "audio/mpeg" })
  const headers = new Map<string, string>()
  if (opts.disposition) headers.set("Content-Disposition", opts.disposition)
  return {
    ok,
    status: ok ? 200 : 404,
    blob: () => Promise.resolve(blob),
    headers: { get: (k: string) => headers.get(k) ?? null },
  } as unknown as Response
}

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => "blob:mock-url")
  URL.revokeObjectURL = vi.fn()
  vi.stubGlobal("localStorage", {
    getItem: () => "sesame",
    setItem: () => {},
    removeItem: () => {},
  })
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe("downloadSong", () => {
  it("走后端 /api/songs/{id}/download 转一手,带着口令(R2 桶没开 CORS,前端不能直连)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(fakeResponse(true))
    vi.stubGlobal("fetch", fetchMock)
    vi.stubGlobal("navigator", { ...navigator, share: undefined, canShare: undefined })
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {})
    await downloadSong("s1", "夏夜的微风")
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain("/api/songs/s1/download")
    expect((init.headers as Record<string, string>)["X-Passcode"]).toBe("sesame")
  })

  it("接口失败时抛错,不触发下载", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeResponse(false)))
    await expect(downloadSong("s1", "夏夜的微风")).rejects.toThrow()
  })

  it("支持文件分享时走系统分享面板,不落到浏览器下载", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        fakeResponse(true, { disposition: 'attachment; filename="download.mp3"' })
      )
    )
    const share = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal("navigator", { ...navigator, share, canShare: () => true })
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click")
    await downloadSong("s1", "夏夜的微风")
    expect(share).toHaveBeenCalled()
    expect(clickSpy).not.toHaveBeenCalled()
  })

  it("分享面板被取消(用户点了取消)时退回浏览器下载", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeResponse(true)))
    const share = vi.fn().mockRejectedValue(new Error("cancelled"))
    vi.stubGlobal("navigator", { ...navigator, share, canShare: () => true })
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {})
    await downloadSong("s1", "夏夜的微风")
    expect(clickSpy).toHaveBeenCalled()
  })

  it("优先用响应头里 filename* 解出来的文件名(后端已经按歌名算好、编码好)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        fakeResponse(true, {
          disposition: "attachment; filename=\"download.mp3\"; filename*=UTF-8''%E6%B5%8B%E8%AF%95.mp3",
        })
      )
    )
    vi.stubGlobal("navigator", { ...navigator, share: undefined, canShare: undefined })
    let downloadAttr = ""
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement
    ) {
      downloadAttr = this.download
    })
    await downloadSong("s1", "随便什么标题")
    expect(downloadAttr).toBe("测试.mp3")
  })

  it("响应头没给文件名时,退回用传入的标题现算一个,做基本的清理", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(fakeResponse(true)))
    vi.stubGlobal("navigator", { ...navigator, share: undefined, canShare: undefined })
    let downloadAttr = ""
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement
    ) {
      downloadAttr = this.download
    })
    await downloadSong("s1", '夏夜/的<微>风"?')
    expect(downloadAttr).toBe("夏夜_的_微_风__.mp3")
  })
})
