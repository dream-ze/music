import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import InspirationList from "@/components/InspirationList"

vi.mock("@/lib/api", () => ({
  getInspirations: vi.fn().mockResolvedValue([
    { title: "深夜的中英说唱", feeling: "hip hop 说唱", lyrics: "[Verse]\nyo", preset: "hiphop.boom_bap" },
  ]),
}))

describe("InspirationList", () => {
  it("点示例时把 lyrics / feeling / preset 一起交给 onPick", async () => {
    const onPick = vi.fn()
    render(<InspirationList onPick={onPick} />)
    fireEvent.click(await screen.findByText("深夜的中英说唱"))
    await waitFor(() =>
      expect(onPick).toHaveBeenCalledWith("[Verse]\nyo", "hip hop 说唱", "hiphop.boom_bap")
    )
  })
})
