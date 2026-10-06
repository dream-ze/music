import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import AdvancedSettings, { type AdvValue } from "@/components/AdvancedSettings"
import type { Styles } from "@/lib/types"

const STYLES: Styles = {
  genres: [
    { id: "pop.ballad", label: "流行抒情", family: "pop" },
    { id: "pop.city_pop", label: "City Pop", family: "pop" },
    { id: "jazz.lounge", label: "爵士", family: "chill" },
  ],
  timbres: [
    { id: "clear", label: "清亮" },
    { id: "breathy", label: "气声" },
  ],
  creativity: [
    { id: "pure", label: "纯正" },
    { id: "normal", label: "常规" },
    { id: "fusion", label: "融合" },
  ],
}

const base: AdvValue = {
  mood: [], vocal_gender: "", language: "", preset: "", vocal_timbre: "", creativity: "normal",
}

const setup = (value: Partial<AdvValue> = {}, styles: Styles | null = STYLES) => {
  const onChange = vi.fn()
  render(<AdvancedSettings value={{ ...base, ...value }} onChange={onChange} styles={styles} />)
  return onChange
}

describe("AdvancedSettings", () => {
  it("曲风按 family 分组,点击发送 id", () => {
    const onChange = setup()
    expect(screen.getByText("流行")).toBeTruthy()          // 分组名
    fireEvent.click(screen.getByText("City Pop"))
    expect(onChange).toHaveBeenCalledWith({ preset: "pop.city_pop" })
  })

  it("曲风「自动」清空 preset", () => {
    const onChange = setup({ preset: "jazz.lounge" })
    fireEvent.click(screen.getByRole("button", { name: "自动曲风" }))
    expect(onChange).toHaveBeenCalledWith({ preset: "" })
  })

  it("选中态按 id 判定", () => {
    setup({ preset: "jazz.lounge", vocal_timbre: "breathy", creativity: "fusion" })
    expect(screen.getByText("爵士").getAttribute("aria-pressed")).toBe("true")
    expect(screen.getByText("City Pop").getAttribute("aria-pressed")).toBe("false")
    expect(screen.getByText("气声").getAttribute("aria-pressed")).toBe("true")
    expect(screen.getByText("融合").getAttribute("aria-pressed")).toBe("true")
  })

  it("人声音色发送 id,「自动」清空", () => {
    const onChange = setup({ vocal_timbre: "clear" })
    fireEvent.click(screen.getByText("气声"))
    expect(onChange).toHaveBeenCalledWith({ vocal_timbre: "breathy" })
    fireEvent.click(screen.getByRole("button", { name: "自动音色" }))
    expect(onChange).toHaveBeenCalledWith({ vocal_timbre: "" })
  })

  it("创意度发送 id", () => {
    const onChange = setup()
    fireEvent.click(screen.getByText("纯正"))
    expect(onChange).toHaveBeenCalledWith({ creativity: "pure" })
  })

  it("情绪 chip 仍发送英文 tag", () => {
    const onChange = setup()
    fireEvent.click(screen.getByText("温柔"))
    expect(onChange).toHaveBeenCalledWith({ mood: ["gentle"] })
  })

  it("选项未加载时显示加载提示", () => {
    setup({}, null)
    expect(screen.getAllByText("加载中…").length).toBeGreaterThan(0)
  })
})
