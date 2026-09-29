import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import CategoryFilterBar from "@/components/CategoryFilterBar"
import { UNCATEGORIZED, type Category } from "@/lib/types"

const categories: Category[] = [
  { id: "c1", name: "民谣", created_by: "ze", created_at: "", song_count: 3 },
]

describe("CategoryFilterBar(手机端分类筛选入口)", () => {
  it("显示全部/未分类/每个自定义分类,带歌曲数", () => {
    render(<CategoryFilterBar categories={categories} active="" onSelect={vi.fn()} />)
    expect(screen.getByText("全部")).toBeInTheDocument()
    expect(screen.getByText("未分类")).toBeInTheDocument()
    expect(screen.getByText("民谣 3")).toBeInTheDocument()
  })

  it("点分类 chip 回调对应的 id", () => {
    const onSelect = vi.fn()
    render(<CategoryFilterBar categories={categories} active="" onSelect={onSelect} />)
    fireEvent.click(screen.getByText("民谣 3"))
    expect(onSelect).toHaveBeenCalledWith("c1")
  })

  it("点未分类回调 UNCATEGORIZED 常量", () => {
    const onSelect = vi.fn()
    render(<CategoryFilterBar categories={categories} active="" onSelect={onSelect} />)
    fireEvent.click(screen.getByText("未分类"))
    expect(onSelect).toHaveBeenCalledWith(UNCATEGORIZED)
  })

  it("点全部回调空字符串", () => {
    const onSelect = vi.fn()
    render(<CategoryFilterBar categories={categories} active="c1" onSelect={onSelect} />)
    fireEvent.click(screen.getByText("全部"))
    expect(onSelect).toHaveBeenCalledWith("")
  })

  it("当前激活的 chip 高亮", () => {
    render(<CategoryFilterBar categories={categories} active="c1" onSelect={vi.fn()} />)
    // 用背景色区分选中态;这里只验证选中项和未选中项的背景不同
    const activeBg = (screen.getByText("民谣 3") as HTMLElement).style.background
    const inactiveBg = (screen.getByText("全部") as HTMLElement).style.background
    expect(activeBg).not.toBe(inactiveBg)
  })
})
