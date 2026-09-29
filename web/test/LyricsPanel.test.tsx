import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import LyricsPanel from "@/components/LyricsPanel"

describe("LyricsPanel", () => {
  it("结构标记行当小标题,唱词逐行显示,空行只留间距", () => {
    const lyrics = "[Verse - rap]\n醒在一个冬天的早上\n\n[Chorus]\n这是我们的 Winter Sweet"
    render(<LyricsPanel lyrics={lyrics} onClose={vi.fn()} />)
    expect(screen.getByText("VERSE - RAP")).toBeInTheDocument()
    expect(screen.getByText("醒在一个冬天的早上")).toBeInTheDocument()
    expect(screen.getByText("CHORUS")).toBeInTheDocument()
    expect(screen.getByText("这是我们的 Winter Sweet")).toBeInTheDocument()
  })

  it("点关闭按钮触发 onClose", () => {
    const onClose = vi.fn()
    render(<LyricsPanel lyrics="[Verse]\n词" onClose={onClose} />)
    fireEvent.click(screen.getByLabelText("关闭歌词"))
    expect(onClose).toHaveBeenCalled()
  })
})
