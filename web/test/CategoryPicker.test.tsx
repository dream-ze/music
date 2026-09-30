import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent, act } from "@testing-library/react"
import CategoryPicker from "@/components/CategoryPicker"
import type { Category } from "@/lib/types"

vi.mock("@/lib/api", () => ({
  createCategory: vi.fn(),
}))

const categories: Category[] = [
  { id: "c1", name: "民谣", created_by: "ze", created_at: "", song_count: 1 },
]

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe("CategoryPicker 打勾反馈", () => {
  it("勾选后短暂提示加入了哪个分类,过一会儿自动消失", () => {
    render(
      <CategoryPicker categories={categories} selectedIds={[]} onToggle={vi.fn()} onClose={vi.fn()} />
    )
    fireEvent.click(screen.getByRole("checkbox"))
    expect(screen.getByText("已加入「民谣」")).toBeInTheDocument()
    act(() => {
      vi.advanceTimersByTime(1600)
    })
    expect(screen.queryByText("已加入「民谣」")).toBeNull()
  })

  it("取消勾选提示移出", () => {
    render(
      <CategoryPicker
        categories={categories}
        selectedIds={["c1"]}
        onToggle={vi.fn()}
        onClose={vi.fn()}
      />
    )
    fireEvent.click(screen.getByRole("checkbox"))
    expect(screen.getByText("已从「民谣」移出")).toBeInTheDocument()
  })

  it("勾选仍然会调用 onToggle", () => {
    const onToggle = vi.fn()
    render(
      <CategoryPicker categories={categories} selectedIds={[]} onToggle={onToggle} onClose={vi.fn()} />
    )
    fireEvent.click(screen.getByRole("checkbox"))
    expect(onToggle).toHaveBeenCalledWith("c1")
  })
})
