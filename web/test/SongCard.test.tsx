import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import SongCard from "@/components/SongCard"
import type { Song } from "@/lib/types"

const song = {
  id: "s1",
  title: "夏夜的微风",
  feeling: "流行 温柔 女声",
  duration_sec: 201,
  mp3_url: "https://r2/s1.mp3",
  created_by: "ze",
  favorite: 0,
} as Song

describe("SongCard", () => {
  it("显示标题与时长,点击触发播放", () => {
    const onPlay = vi.fn()
    render(<SongCard song={song} onPlay={onPlay} />)
    expect(screen.getByText("夏夜的微风")).toBeInTheDocument()
    expect(screen.getByText("03:21")).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText("播放"))
    expect(onPlay).toHaveBeenCalledWith(song)
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
})
