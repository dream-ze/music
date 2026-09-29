import { describe, it, expect } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { PlayerProvider, usePlayer } from "@/lib/player"
import Player from "@/components/Player"
import type { Song } from "@/lib/types"

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
