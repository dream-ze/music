import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { PlayerProvider, usePlayer } from "@/lib/player"
import Player from "@/components/Player"
import { downloadSong } from "@/lib/download"
import type { Song } from "@/lib/types"

vi.mock("@/lib/download", () => ({
  downloadSong: vi.fn().mockResolvedValue(undefined),
}))

const song = { id: "s1", title: "冬日甜心", duration_sec: 45, mp3_url: "https://r2/s1.mp3" } as Song

function Harness() {
  const { play } = usePlayer()
  return <button onClick={() => play(song)}>play</button>
}

describe("Player 歌词入口", () => {
  it("有歌播放时,“词”是指向 /now-playing 的链接", () => {
    render(
      <PlayerProvider>
        <Harness />
        <Player />
      </PlayerProvider>
    )
    fireEvent.click(screen.getByText("play"))
    const link = screen.getByLabelText("查看歌词")
    expect(link.tagName).toBe("A")
    expect(link.getAttribute("href")).toBe("/now-playing")
  })

  it("没有播放时整条播放条不渲染", () => {
    render(
      <PlayerProvider>
        <Player />
      </PlayerProvider>
    )
    expect(screen.queryByLabelText("查看歌词")).toBeNull()
  })
})

describe("Player 下载", () => {
  it("点下载按钮调用 downloadSong,带上当前播放歌曲的 id 和标题", async () => {
    render(
      <PlayerProvider>
        <Harness />
        <Player />
      </PlayerProvider>
    )
    fireEvent.click(screen.getByText("play"))
    fireEvent.click(screen.getByLabelText("下载"))
    await waitFor(() => expect(downloadSong).toHaveBeenCalledWith("s1", "冬日甜心"))
  })
})
