import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent, act } from "@testing-library/react"
import Library from "@/app/library/page"
import { listSongs, listActiveJobs, listCategories, deleteCategory } from "@/lib/api"

vi.mock("@/lib/api", () => ({
  listSongs: vi.fn(),
  listActiveJobs: vi.fn(),
  listCategories: vi.fn().mockResolvedValue([]),
  deleteCategory: vi.fn().mockResolvedValue(undefined),
  toggleFavorite: vi.fn(),
}))
vi.mock("@/lib/player", () => ({ usePlayer: () => ({ play: vi.fn() }) }))
let searchParams = new URLSearchParams()
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => searchParams,
}))

const song = {
  id: "s1", title: "旧歌", lyrics: "", feeling: "流行", spec_json: "{}", structured_lyrics: "",
  seed: null, mp3_url: "", duration_sec: 45, instrumental: 0, created_by: "demo",
  favorite: 0, created_at: "",
}
const job = { job_id: "j1", status: "running" as const, title: "冬日甜心", feeling: "女声", created_by: "demo", created_at: "" }

describe("作品库生成中卡片", () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.mocked(listSongs).mockResolvedValue([song])
  })
  afterEach(() => vi.useRealTimers())

  it("生成中的任务排在歌曲前面;任务消失后重拉歌曲列表", async () => {
    vi.mocked(listActiveJobs).mockResolvedValueOnce([job]).mockResolvedValueOnce([])
    render(<Library />)
    await act(async () => {})
    const titles = screen.getAllByText(/冬日甜心|旧歌/).map((el) => el.textContent)
    expect(titles).toEqual(["冬日甜心", "旧歌"])
    expect(listSongs).toHaveBeenCalledTimes(1)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(screen.queryByText("冬日甜心")).toBeNull()
    expect(listSongs).toHaveBeenCalledTimes(2)
  })

  it("输入搜索词时不显示生成中卡片", async () => {
    vi.mocked(listActiveJobs).mockResolvedValue([job])
    render(<Library />)
    await act(async () => {})
    expect(screen.getByText("冬日甜心")).toBeInTheDocument()
    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText("🔍 搜索歌名、风格、歌词"), { target: { value: "x" } })
    })
    expect(screen.queryByText("冬日甜心")).toBeNull()
  })
})

describe("作品库「选择歌曲」入口(打开分类,像网易云歌单一样选歌加进来)", () => {
  beforeEach(() => {
    vi.mocked(listSongs).mockResolvedValue([song])
    vi.mocked(listActiveJobs).mockResolvedValue([])
  })
  afterEach(() => {
    searchParams = new URLSearchParams()
  })

  it("没有按分类筛选时不显示「选择歌曲」", async () => {
    render(<Library />)
    await act(async () => {})
    expect(screen.queryByText("+ 选择歌曲")).toBeNull()
  })

  it("按真实分类筛选时显示「选择歌曲」,点开会弹出选歌面板", async () => {
    searchParams = new URLSearchParams("cat=c1")
    vi.mocked(listCategories).mockResolvedValue([
      { id: "c1", name: "民谣", created_by: "ze", created_at: "", song_count: 1 },
    ])
    render(<Library />)
    await act(async () => {})
    const entry = screen.getByText("+ 选择歌曲")
    await act(async () => {
      fireEvent.click(entry)
    })
    expect(screen.getByText("选择歌曲 · 民谣")).toBeInTheDocument()
  })

  it("按「未分类」筛选时不显示「选择歌曲」(未分类不是能塞歌进去的容器)", async () => {
    searchParams = new URLSearchParams("cat=__none__")
    render(<Library />)
    await act(async () => {})
    expect(screen.queryByText("+ 选择歌曲")).toBeNull()
  })
})

describe("作品库分类 chip 删除(手机端没有侧栏,补在这排 chip 上)", () => {
  beforeEach(() => {
    vi.mocked(listSongs).mockResolvedValue([song])
    vi.mocked(listActiveJobs).mockResolvedValue([])
    vi.mocked(listCategories).mockResolvedValue([
      { id: "c1", name: "民谣", created_by: "ze", created_at: "", song_count: 0 },
    ])
  })
  afterEach(() => {
    searchParams = new URLSearchParams()
  })

  it("取消确认框不会调用删除接口", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false)
    render(<Library />)
    await act(async () => {})
    fireEvent.click(screen.getByLabelText("删除分类"))
    expect(deleteCategory).not.toHaveBeenCalled()
  })

  it("确认后调用删除接口,并重新拉取分类和歌曲列表", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true)
    render(<Library />)
    await act(async () => {})
    const before = vi.mocked(listSongs).mock.calls.length
    await act(async () => {
      fireEvent.click(screen.getByLabelText("删除分类"))
    })
    expect(deleteCategory).toHaveBeenCalledWith("c1")
    expect(vi.mocked(listSongs).mock.calls.length).toBeGreaterThan(before)
  })
})
