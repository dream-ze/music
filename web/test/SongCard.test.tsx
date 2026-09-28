import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import SongCard from "@/components/SongCard"
import { deleteSong, setSongCategory } from "@/lib/api"
import { SONG_DRAG_MIME, type Song, type Category } from "@/lib/types"

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  deleteSong: vi.fn().mockResolvedValue(undefined),
  setSongCategory: vi.fn().mockResolvedValue(undefined),
}))

const song = {
  id: "s1",
  title: "夏夜的微风",
  feeling: "流行 温柔 女声",
  duration_sec: 201,
  mp3_url: "https://r2/s1.mp3",
  created_by: "ze",
  favorite: 0,
} as Song

afterEach(() => vi.restoreAllMocks())

describe("SongCard", () => {
  it("显示标题与时长,点击触发播放", () => {
    const onPlay = vi.fn()
    render(<SongCard song={song} onPlay={onPlay} />)
    expect(screen.getByText("夏夜的微风")).toBeInTheDocument()
    expect(screen.getByText("03:21")).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText("播放"))
    expect(onPlay).toHaveBeenCalledWith(song)
  })

  it("不再显示 @created_by", () => {
    render(<SongCard song={song} onPlay={vi.fn()} />)
    expect(screen.queryByText("@ze")).not.toBeInTheDocument()
  })

  it("卡片可拖拽,拖拽开始时把歌曲 id 写进 dataTransfer", () => {
    render(<SongCard song={song} onPlay={vi.fn()} />)
    const card = screen.getByText("夏夜的微风").closest('[draggable="true"]')
    expect(card).not.toBeNull()
    const setData = vi.fn()
    fireEvent.dragStart(card as Element, { dataTransfer: { setData } })
    expect(setData).toHaveBeenCalledWith(SONG_DRAG_MIME, "s1")
  })
})

describe("SongCard 归类", () => {
  const categories: Category[] = [
    { id: "c1", name: "民谣", created_by: "ze", created_at: "", song_count: 1 },
    { id: "c2", name: "说唱", created_by: "ze", created_at: "", song_count: 0 },
  ]

  it("不传 categories 时不显示归类下拉框", () => {
    render(<SongCard song={song} onPlay={vi.fn()} />)
    expect(screen.queryByLabelText("分类")).toBeNull()
  })

  it("传 categories 时显示下拉框,默认选中未分类", () => {
    render(<SongCard song={song} onPlay={vi.fn()} categories={categories} />)
    expect(screen.getByLabelText("分类")).toHaveValue("")
  })

  it("选择分类会调用接口并回调 onCategoryChanged", async () => {
    const onCategoryChanged = vi.fn()
    render(
      <SongCard
        song={song}
        onPlay={vi.fn()}
        categories={categories}
        onCategoryChanged={onCategoryChanged}
      />
    )
    fireEvent.change(screen.getByLabelText("分类"), { target: { value: "c1" } })
    await waitFor(() => expect(setSongCategory).toHaveBeenCalledWith("s1", "c1"))
    await waitFor(() => expect(onCategoryChanged).toHaveBeenCalledWith("s1", "c1"))
  })

  it("已有分类的歌显示当前选中项", () => {
    const categorized = { ...song, category_id: "c2" } as Song
    render(<SongCard song={categorized} onPlay={vi.fn()} categories={categories} />)
    expect(screen.getByLabelText("分类")).toHaveValue("c2")
  })
})

describe("SongCard 删除", () => {
  it("取消确认框不会调用删除接口", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false)
    render(<SongCard song={song} onPlay={vi.fn()} onDeleted={vi.fn()} />)
    fireEvent.click(screen.getByLabelText("删除"))
    expect(deleteSong).not.toHaveBeenCalled()
  })

  it("确认后调用删除接口并回调 onDeleted", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true)
    const onDeleted = vi.fn()
    render(<SongCard song={song} onPlay={vi.fn()} onDeleted={onDeleted} />)
    fireEvent.click(screen.getByLabelText("删除"))
    await waitFor(() => expect(deleteSong).toHaveBeenCalledWith("s1"))
    await waitFor(() => expect(onDeleted).toHaveBeenCalledWith("s1"))
  })
})

describe("SongCard 降级标记", () => {
  it("有阶段回退时显示降级标记,并说明是哪个阶段", () => {
    const degraded = {
      ...song,
      llm_status: JSON.stringify([
        { stage: "歌曲规划", ok: false },
        { stage: "歌词整理", ok: true },
      ]),
    } as Song
    render(<SongCard song={degraded} onPlay={vi.fn()} />)
    const badge = screen.getByTitle(/歌曲规划/)
    expect(badge).toBeInTheDocument()
  })

  it("全部阶段正常时不显示降级标记", () => {
    const ok = {
      ...song,
      llm_status: JSON.stringify([{ stage: "歌曲规划", ok: true }]),
    } as Song
    render(<SongCard song={ok} onPlay={vi.fn()} />)
    expect(screen.queryByText("降级")).not.toBeInTheDocument()
  })

  it("老歌没有 llm_status 时不显示降级标记", () => {
    render(<SongCard song={song} onPlay={vi.fn()} />)
    expect(screen.queryByText("降级")).not.toBeInTheDocument()
  })

  it("降级说明按阶段列出 reason 文案", () => {
    const degraded = {
      ...song,
      llm_status: JSON.stringify([
        { stage: "歌曲规划", ok: false, reason: "non_english" },
        { stage: "歌词整理", ok: false, reason: "text_changed" },
      ]),
    } as Song
    render(<SongCard song={degraded} onPlay={vi.fn()} />)
    const title = screen.getByText("降级").getAttribute("title") || ""
    expect(title).toContain("歌曲规划：模型输出含中文")
    expect(title).toContain("歌词整理：模型改动了歌词，已用规则断行")
  })

  it("没有 reason 的旧事件仍能显示", () => {
    const degraded = {
      ...song,
      llm_status: JSON.stringify([{ stage: "歌曲规划", ok: false }]),
    } as Song
    render(<SongCard song={degraded} onPlay={vi.fn()} />)
    expect(screen.getByText("降级").getAttribute("title")).toContain("歌曲规划：已回退")
  })
})
