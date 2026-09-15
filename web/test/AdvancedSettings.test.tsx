import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import AdvancedSettings, { type AdvValue } from "@/components/AdvancedSettings"

const base: AdvValue = {
  genre: [], mood: [], vocal_gender: "", language: "", length: "full", seed: "", preset: "",
}

describe("AdvancedSettings 发送英文 tag 与 preset", () => {
  it("点中文风格 chip 发送英文 tag", () => {
    const onChange = vi.fn()
    render(<AdvancedSettings value={base} onChange={onChange} />)
    fireEvent.click(screen.getByText("流行"))
    expect(onChange).toHaveBeenCalledWith({ genre: ["pop"] })
  })

  it("点情绪 chip 发送英文 tag", () => {
    const onChange = vi.fn()
    render(<AdvancedSettings value={base} onChange={onChange} />)
    fireEvent.click(screen.getByText("温柔"))
    expect(onChange).toHaveBeenCalledWith({ mood: ["gentle"] })
  })

  it("选 Hip hop 且未选 preset 时默认落到 boom bap", () => {
    const onChange = vi.fn()
    render(<AdvancedSettings value={base} onChange={onChange} />)
    fireEvent.click(screen.getByText("Hip hop"))
    expect(onChange).toHaveBeenCalledWith({ genre: ["hip hop"], preset: "hiphop.boom_bap" })
  })

  it("已选 preset 时选 Hip hop 不改 preset", () => {
    const onChange = vi.fn()
    render(<AdvancedSettings value={{ ...base, preset: "hiphop.trap" }} onChange={onChange} />)
    fireEvent.click(screen.getByText("Hip hop"))
    expect(onChange).toHaveBeenCalledWith({ genre: ["hip hop"] })
  })

  it("preset 分段控件发送 id", () => {
    const onChange = vi.fn()
    render(<AdvancedSettings value={base} onChange={onChange} />)
    fireEvent.click(screen.getByText("Trap"))
    expect(onChange).toHaveBeenCalledWith({ preset: "hiphop.trap" })
  })

  it("chip 选中态按英文 tag 判定", () => {
    render(<AdvancedSettings value={{ ...base, genre: ["pop"] }} onChange={vi.fn()} />)
    expect(screen.getByText("流行").getAttribute("aria-pressed")).toBe("true")
    expect(screen.getByText("摇滚").getAttribute("aria-pressed")).toBe("false")
  })
})
