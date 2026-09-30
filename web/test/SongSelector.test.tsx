import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import SongSelector from "@/components/SongSelector"
import { listSongs, addSongToCategory, removeSongFromCategory } from "@/lib/api"
import type { Song } from "@/lib/types"

vi.mock("@/lib/api", () => ({
  listSongs: vi.fn(),
  addSongToCategory: vi.fn().mockResolvedValue([]),
  removeSongFromCategory: vi.fn().mockResolvedValue([]),
}))

const songs: Song[] = [
  { id: "s1", title: "夏夜的微风", feeling: "流行", category_ids: ["c1"] } as unknown as Song,
  { id: "s2", title: "冬日甜心", feeling: "hip hop", category_ids: [] } as unknown as Song,
]

afterEach(() => vi.restoreAllMocks())

describe("SongSelector 打开分类选择歌曲", () => {
  it("加载后列出所有歌曲,已在这个分类里的默认打勾", async () => {
    vi.mocked(listSongs).mockResolvedValue(songs)
    render(
      <SongSelector categoryId="c1" categoryName="民谣" onClose={vi.fn()} />
    )
    await waitFor(() => expect(screen.getByText("夏夜的微风")).toBeInTheDocument())
    const checkboxes = screen.getAllByRole("checkbox") as HTMLInputElement[]
    expect(checkboxes[0].checked).toBe(true)
    expect(checkboxes[1].checked).toBe(false)
  })

  it("勾选未在里面的歌会调用加入接口", async () => {
    vi.mocked(listSongs).mockResolvedValue(songs)
    const onChanged = vi.fn()
    render(
      <SongSelector categoryId="c1" categoryName="民谣" onClose={vi.fn()} onChanged={onChanged} />
    )
    await waitFor(() => screen.getByText("冬日甜心"))
    const checkboxes = screen.getAllByRole("checkbox")
    fireEvent.click(checkboxes[1])
    await waitFor(() => expect(addSongToCategory).toHaveBeenCalledWith("s2", "c1"))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })

  it("取消勾选已在里面的歌会调用移出接口", async () => {
    vi.mocked(listSongs).mockResolvedValue(songs)
    render(<SongSelector categoryId="c1" categoryName="民谣" onClose={vi.fn()} />)
    await waitFor(() => screen.getByText("夏夜的微风"))
    const checkboxes = screen.getAllByRole("checkbox")
    fireEvent.click(checkboxes[0])
    await waitFor(() => expect(removeSongFromCategory).toHaveBeenCalledWith("s1", "c1"))
  })

  it("没有歌曲时显示空状态", async () => {
    vi.mocked(listSongs).mockResolvedValue([])
    render(<SongSelector categoryId="c1" categoryName="民谣" onClose={vi.fn()} />)
    await waitFor(() => expect(screen.getByText("还没有歌曲")).toBeInTheDocument())
  })

  it("点关闭按钮触发 onClose", async () => {
    vi.mocked(listSongs).mockResolvedValue(songs)
    const onClose = vi.fn()
    render(<SongSelector categoryId="c1" categoryName="民谣" onClose={onClose} />)
    await waitFor(() => screen.getByText("夏夜的微风"))
    fireEvent.click(screen.getByLabelText("关闭"))
    expect(onClose).toHaveBeenCalled()
  })
})
