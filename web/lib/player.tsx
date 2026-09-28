"use client"
import { createContext, useContext, useState } from "react"
import type { Song } from "./types"

interface PlayerCtx {
  current: Song | null
  play: (song: Song) => void
  stop: () => void
}
const Ctx = createContext<PlayerCtx>({ current: null, play: () => {}, stop: () => {} })

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const [current, setCurrent] = useState<Song | null>(null)
  return (
    <Ctx.Provider value={{ current, play: setCurrent, stop: () => setCurrent(null) }}>
      {children}
    </Ctx.Provider>
  )
}

export function usePlayer() {
  return useContext(Ctx)
}
