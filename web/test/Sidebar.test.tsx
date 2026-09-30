import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import Sidebar from "@/components/Sidebar"
import {
  listCategories,
  createCategory,
  deleteCategory,
  addSongToCategory,
} from "@/lib/api"
import { SONG_DRAG_MIME } from "@/lib/types"

const push = vi.fn()
let searchParams = new URLSearchParams()

vi.mock("@/lib/api", () => ({
  listCategories: vi.fn(),
  createCategory: vi.fn(),
  deleteCategory: vi.fn(),
  addSongToCategory: vi.fn(),
}))
vi.mock("next/navigation", () => ({
  usePathname: () => "/library",
  useSearchParams: () => searchParams,
  useRouter: () => ({ push }),
}))

const categories = [
  { id: "c1", name: "民谣", created_by: "ze", created_at: "", song_count: 2 },
]

afterEach(() => {
  vi.clearAllMocks()
  searchParams = new URLSearchParams()
})

describe("Sidebar 自定义分类", () => {
  it("加载后显示分类名和歌曲数,以及固定的未分类入口", async () => {
    vi.mocked(listCategories).mockResolvedValue(categories)
    render(<Sidebar />)
    await waitFor(() => expect(screen.getByText("民谣")).toBeInTheDocument())
    expect(screen.getByText("2")).toBeInTheDocument()
    expect(screen.getByText("未分类")).toBeInTheDocument()
  })

  it("点分类名跳转到对应的作品库筛选页", async () => {
    vi.mocked(listCategories).mockResolvedValue(categories)
    render(<Sidebar />)
    await waitFor(() => screen.getByText("民谣"))
    fireEvent.click(screen.getByText("民谣"))
    expect(push).toHaveBeenCalledWith("/library?cat=c1")
  })

  it("新建分类:输入名称回车后调用接口并刷新列表", async () => {
    vi.mocked(listCategories).mockResolvedValue([])
    vi.mocked(createCategory).mockResolvedValue({
      id: "c2", name: "治愈", created_by: "ze", created_at: "", song_count: 0,
    })
    render(<Sidebar />)
    await waitFor(() => screen.getByPlaceholderText("+ 新建分类"))
    fireEvent.change(screen.getByPlaceholderText("+ 新建分类"), {
      target: { value: "治愈" },
    })
    fireEvent.keyDown(screen.getByPlaceholderText("+ 新建分类"), { key: "Enter" })
    await waitFor(() => expect(createCategory).toHaveBeenCalledWith("治愈"))
    expect(listCategories).toHaveBeenCalledTimes(2) // 初次加载 + 新建后刷新
  })

  it("删除分类需要二次确认,确认后调用接口", async () => {
    vi.mocked(listCategories).mockResolvedValue(categories)
    vi.mocked(deleteCategory).mockResolvedValue(undefined)
    vi.spyOn(window, "confirm").mockReturnValue(true)
    render(<Sidebar />)
    await waitFor(() => screen.getByText("民谣"))
    fireEvent.click(screen.getByLabelText("删除分类"))
    expect(window.confirm).toHaveBeenCalled()
    await waitFor(() => expect(deleteCategory).toHaveBeenCalledWith("c1"))
  })

  it("取消确认框不会调用删除接口", async () => {
    vi.mocked(listCategories).mockResolvedValue(categories)
    vi.spyOn(window, "confirm").mockReturnValue(false)
    render(<Sidebar />)
    await waitFor(() => screen.getByText("民谣"))
    fireEvent.click(screen.getByLabelText("删除分类"))
    expect(deleteCategory).not.toHaveBeenCalled()
  })

  it("把歌拖到分类项上是「加进去」,不是「挪过去」", async () => {
    vi.mocked(listCategories).mockResolvedValue(categories)
    vi.mocked(addSongToCategory).mockResolvedValue(["c1"])
    render(<Sidebar />)
    await waitFor(() => screen.getByText("民谣"))
    const dataTransfer = { getData: (t: string) => (t === SONG_DRAG_MIME ? "s1" : "") }
    fireEvent.drop(screen.getByText("民谣"), { dataTransfer })
    await waitFor(() => expect(addSongToCategory).toHaveBeenCalledWith("s1", "c1"))
  })

  it("未分类只能点击筛选,不接收拖拽(一首歌能同时属于好几个分类,拖过去没有唯一含义)", async () => {
    vi.mocked(listCategories).mockResolvedValue(categories)
    render(<Sidebar />)
    await waitFor(() => screen.getByText("未分类"))
    const dataTransfer = { getData: (t: string) => (t === SONG_DRAG_MIME ? "s1" : "") }
    fireEvent.drop(screen.getByText("未分类"), { dataTransfer })
    expect(addSongToCategory).not.toHaveBeenCalled()
  })
})
