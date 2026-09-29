import { describe, it, expect } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { PlayerProvider, usePlayer } from "@/lib/player"
import Player from "@/components/Player"
import type { Song } from "@/lib/types"

const withLyrics = {
  id: "s1", title: "冬日甜心", duration_sec: 45, mp3_url: "https://r2/s1.mp3",
  structured_lyrics: "[Verse]\n醒在一个冬天的早上",
} as Song

const withoutLyrics = { id: "s2", title: "旧歌", duration_sec: 45, mp3_url: "https://r2/s2.mp3" } as Song

function Harness({ song }: { song: Song }) {
  const { play } = usePlayer()
  return <button onClick={() => play(song)}>play</button>
}

describe("Player 歌词面板", () => {
  it("有歌词时点“词”弹出面板,再点一次收起", () => {
    render(
      <PlayerProvider>
        <Harness song={withLyrics} />
        <Player />
      </PlayerProvider>
    )
    fireEvent.click(screen.getByText("play"))
    expect(screen.queryByText("醒在一个冬天的早上")).toBeNull()

    fireEvent.click(screen.getByLabelText("歌词"))
    expect(screen.getByText("醒在一个冬天的早上")).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText("歌词"))
    expect(screen.queryByText("醒在一个冬天的早上")).toBeNull()
  })

  it("点面板的关闭按钮也能收起", () => {
    render(
      <PlayerProvider>
        <Harness song={withLyrics} />
        <Player />
      </PlayerProvider>
    )
    fireEvent.click(screen.getByText("play"))
    fireEvent.click(screen.getByLabelText("歌词"))
    fireEvent.click(screen.getByLabelText("关闭歌词"))
    expect(screen.queryByText("醒在一个冬天的早上")).toBeNull()
  })

  it("没有歌词时“词”按钮禁用", () => {
    render(
      <PlayerProvider>
        <Harness song={withoutLyrics} />
        <Player />
      </PlayerProvider>
    )
    fireEvent.click(screen.getByText("play"))
    expect(screen.getByLabelText("歌词")).toBeDisabled()
  })
})
