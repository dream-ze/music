"use client"
import { useEffect, useState } from "react"
import { listSongs } from "@/lib/api"
import SongCard from "@/components/SongCard"
import { usePlayer } from "@/lib/player"
import type { Song } from "@/lib/types"

export default function Favorites() {
  const { play } = usePlayer()
  const [songs, setSongs] = useState<Song[]>([])
  useEffect(() => {
    listSongs({ favorite: true })
      .then(setSongs)
      .catch(() => setSongs([]))
  }, [])
  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 800, margin: "0 0 18px" }}>我的收藏</h1>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14 }}>
        {songs.map((s) => (
          <SongCard key={s.id} song={s} onPlay={play} />
        ))}
      </div>
      {songs.length === 0 && <p className="text-muted">还没有收藏</p>}
    </div>
  )
}
