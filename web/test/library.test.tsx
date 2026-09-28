import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent, act } from "@testing-library/react"
import Library from "@/app/library/page"
import { listSongs, listActiveJobs } from "@/lib/api"

vi.mock("@/lib/api", () => ({
  listSongs: vi.fn(),
  listActiveJobs: vi.fn(),
  listCategories: vi.fn().mockResolvedValue([]),
  toggleFavorite: vi.fn(),
}))
vi.mock("@/lib/player", () => ({ usePlayer: () => ({ play: vi.fn() }) }))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
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
