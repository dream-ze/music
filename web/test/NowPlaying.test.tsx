import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { useEffect } from "react"
import NowPlaying from "@/app/now-playing/page"
import { PlayerProvider, usePlayer } from "@/lib/player"
import type { Song } from "@/lib/types"

const back = vi.fn()
vi.mock("next/navigation", () => ({
  useRouter: () => ({ back }),
}))

const songWithLyrics = {
  id: "s1", title: "冬日甜心", feeling: "女声 hip hop",
  structured_lyrics: "[Verse - rap]\n醒在一个冬天的早上\n\n[Chorus]\n这是我们的 Winter Sweet",
} as Song

const songWithoutLyrics = { id: "s2", title: "旧歌", feeling: "" } as Song

function withSong(song: Song | null) {
  function Harness() {
    const { play } = usePlayer()
    useEffect(() => {
      if (song) play(song)
    }, [play])
    return null
  }
  return (
    <PlayerProvider>
      <Harness />
      <NowPlaying />
    </PlayerProvider>
  )
}

describe("NowPlaying 全屏歌词页", () => {
  it("没有播放时显示空状态和返回作品库的链接", () => {
    render(
      <PlayerProvider>
        <NowPlaying />
      </PlayerProvider>
    )
    expect(screen.getByText("还没有播放的歌曲")).toBeInTheDocument()
    expect(screen.getByText("去作品库看看 →").closest("a")).toHaveAttribute("href", "/library")
  })

  it("有歌词时显示标题、感觉、结构标题和逐行歌词", () => {
    render(withSong(songWithLyrics))
    expect(screen.getByText("冬日甜心")).toBeInTheDocument()
    expect(screen.getByText("女声 hip hop")).toBeInTheDocument()
    expect(screen.getByText("VERSE - RAP")).toBeInTheDocument()
    expect(screen.getByText("醒在一个冬天的早上")).toBeInTheDocument()
    expect(screen.getByText("CHORUS")).toBeInTheDocument()
    expect(screen.getByText("这是我们的 Winter Sweet")).toBeInTheDocument()
  })

  it("没有歌词的老歌显示“暂无歌词”", () => {
    render(withSong(songWithoutLyrics))
    expect(screen.getByText("暂无歌词")).toBeInTheDocument()
  })

  it("点返回调用 router.back", () => {
    render(withSong(songWithLyrics))
    fireEvent.click(screen.getByText("‹ 返回"))
    expect(back).toHaveBeenCalled()
  })
})
