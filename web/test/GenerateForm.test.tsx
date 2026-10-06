import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import GenerateForm from "@/components/GenerateForm"
import { generate } from "@/lib/api"

vi.mock("@/lib/api", () => ({
  generate: vi.fn().mockResolvedValue({ job_id: "j1" }),
  getJob: vi.fn().mockResolvedValue({ status: "done", song: null }),
  getStyles: vi.fn().mockResolvedValue({
    genres: [{ id: "jazz.lounge", label: "爵士", family: "chill" }],
    timbres: [{ id: "breathy", label: "气声" }],
    creativity: [
      { id: "pure", label: "纯正" },
      { id: "normal", label: "常规" },
      { id: "fusion", label: "融合" },
    ],
  }),
}))
vi.mock("@/lib/player", () => ({ usePlayer: () => ({ play: vi.fn() }) }))

describe("GenerateForm 歌名", () => {
  it("填写的歌名随提交一起发给后端", async () => {
    render(<GenerateForm />)
    fireEvent.change(screen.getByPlaceholderText("不填则自动命名"), {
      target: { value: "  我的歌 " },
    })
    fireEvent.click(screen.getByText("✦ 生成我的歌曲"))
    await waitFor(() => expect(generate).toHaveBeenCalled())
    expect(vi.mocked(generate).mock.calls[0][0].title).toBe("我的歌")
  })
  it("曲风/音色/创意度随提交发送,不再发送 genre", async () => {
    vi.mocked(generate).mockClear()
    render(<GenerateForm />)
    fireEvent.click(await screen.findByText("爵士"))
    fireEvent.click(screen.getByText("气声"))
    fireEvent.click(screen.getByText("融合"))
    fireEvent.click(screen.getByText("✦ 生成我的歌曲"))
    await waitFor(() => expect(generate).toHaveBeenCalled())
    const o = vi.mocked(generate).mock.calls[0][0].overrides
    expect(o).toMatchObject({ preset: "jazz.lounge", vocal_timbre: "breathy", creativity: "fusion" })
    expect(o.genre).toBeUndefined()
  })

  it("纯音乐开关随提交发送,并让歌词变为可选", async () => {
    vi.mocked(generate).mockClear()
    render(<GenerateForm />)
    fireEvent.click(screen.getByLabelText("纯音乐（无人声）"))
    expect(screen.getByPlaceholderText("纯音乐无需歌词")).toBeTruthy()
    fireEvent.click(screen.getByText("✦ 生成我的歌曲"))
    await waitFor(() => expect(generate).toHaveBeenCalled())
    expect(vi.mocked(generate).mock.calls[0][0].instrumental).toBe(true)
  })
})
