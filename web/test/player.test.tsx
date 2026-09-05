import { describe, it, expect } from "vitest"
import { render, screen, act } from "@testing-library/react"
import { PlayerProvider, usePlayer } from "@/lib/player"
import type { Song } from "@/lib/types"

function Probe() {
  const { current, play } = usePlayer()
  return (
    <div>
      <span data-testid="cur">{current?.title ?? "无"}</span>
      <button onClick={() => play({ id: "s1", title: "夏夜" } as Song)}>play</button>
    </div>
  )
}

describe("player store", () => {
  it("play 后 current 更新", () => {
    render(
      <PlayerProvider>
        <Probe />
      </PlayerProvider>
    )
    expect(screen.getByTestId("cur").textContent).toBe("无")
    act(() => {
      screen.getByText("play").click()
    })
    expect(screen.getByTestId("cur").textContent).toBe("夏夜")
  })
})
