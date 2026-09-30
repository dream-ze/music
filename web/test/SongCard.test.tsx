import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import SongCard from "@/components/SongCard"
import { deleteSong, addSongToCategory, removeSongFromCategory, createCategory } from "@/lib/api"
import { SONG_DRAG_MIME, type Song, type Category } from "@/lib/types"

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  deleteSong: vi.fn().mockResolvedValue(undefined),
  addSongToCategory: vi.fn().mockResolvedValue([]),
  removeSongFromCategory: vi.fn().mockResolvedValue([]),
  createCategory: vi.fn(),
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

describe("SongCard 归类(多对多,跟网易云歌单一样)", () => {
  const categories: Category[] = [
    { id: "c1", name: "民谣", created_by: "ze", created_at: "", song_count: 1 },
    { id: "c2", name: "说唱", created_by: "ze", created_at: "", song_count: 0 },
  ]

  it("没有归类时只显示「+ 分类」,不显示任何标签", () => {
    render(<SongCard song={song} onPlay={vi.fn()} categories={categories} />)
    expect(screen.getByLabelText("添加到分类")).toBeInTheDocument()
    expect(screen.queryByText("民谣")).toBeNull()
  })

  it("已归类的歌在卡片上直接显示标签(不用打开面板就能看到)", () => {
    const tagged = { ...song, category_ids: ["c1", "c2"] } as Song
    render(<SongCard song={tagged} onPlay={vi.fn()} categories={categories} />)
    expect(screen.getByText("民谣")).toBeInTheDocument()
    expect(screen.getByText("说唱")).toBeInTheDocument()
  })

  it("点「+ 分类」打开面板,勾选后调用添加接口、卡片上出现标签", async () => {
    const onCategoryChanged = vi.fn()
    render(
      <SongCard
        song={song}
        onPlay={vi.fn()}
        categories={categories}
        onCategoryChanged={onCategoryChanged}
      />
    )
    fireEvent.click(screen.getByLabelText("添加到分类"))
    fireEvent.click(screen.getAllByText("民谣")[0].closest("label")!.querySelector("input")!)
    await waitFor(() => expect(addSongToCategory).toHaveBeenCalledWith("s1", "c1"))
    await waitFor(() => expect(onCategoryChanged).toHaveBeenCalledWith("s1", ["c1"]))
  })

  it("再次勾选(取消)已选中的分类会调用移除接口,两个分类互不影响", async () => {
    const tagged = { ...song, category_ids: ["c1", "c2"] } as Song
    render(<SongCard song={tagged} onPlay={vi.fn()} categories={categories} />)
    fireEvent.click(screen.getByLabelText("添加到分类"))
    const folkCheckbox = screen.getAllByText("民谣")
      .map((el) => el.closest("label"))
      .find((el) => el?.querySelector("input"))!
      .querySelector("input")!
    fireEvent.click(folkCheckbox)
    await waitFor(() => expect(removeSongFromCategory).toHaveBeenCalledWith("s1", "c1"))
    // 说唱(c2)不受影响,卡片上还留着
    expect(screen.getAllByText("说唱").length).toBeGreaterThan(0)
  })

  it("面板里可以直接新建分类,不用去侧栏", async () => {
    vi.mocked(createCategory).mockResolvedValue({
      id: "c3", name: "治愈", created_by: "ze", created_at: "", song_count: 0,
    })
    const onCategoriesChanged = vi.fn()
    render(
      <SongCard
        song={song}
        onPlay={vi.fn()}
        categories={categories}
        onCategoriesChanged={onCategoriesChanged}
      />
    )
    fireEvent.click(screen.getByLabelText("添加到分类"))
    fireEvent.change(screen.getByPlaceholderText("+ 新建分类"), { target: { value: "治愈" } })
    fireEvent.click(screen.getByText("确定"))
    await waitFor(() => expect(createCategory).toHaveBeenCalledWith("治愈"))
    await waitFor(() => expect(onCategoriesChanged).toHaveBeenCalled())
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

  it("接口还没返回时显示“删除中…”,接口是真实网络请求,不给提示会像卡住", () => {
    vi.spyOn(window, "confirm").mockReturnValue(true)
    render(<SongCard song={song} onPlay={vi.fn()} />)
    fireEvent.click(screen.getByLabelText("删除"))
    expect(screen.getByText("删除中…")).toBeInTheDocument()
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
