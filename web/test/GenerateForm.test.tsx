import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import GenerateForm from "@/components/GenerateForm"
import { generate } from "@/lib/api"

vi.mock("@/lib/api", () => ({
  generate: vi.fn().mockResolvedValue({ job_id: "j1" }),
  getJob: vi.fn().mockResolvedValue({ status: "done", song: null }),
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
})
