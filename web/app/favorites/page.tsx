"use client"
import { useEffect, useState } from "react"
import { listSongs, listCategories } from "@/lib/api"
import SongCard from "@/components/SongCard"
import { usePlayer } from "@/lib/player"
import type { Song, Category } from "@/lib/types"

export default function Favorites() {
  const { play } = usePlayer()
  const [songs, setSongs] = useState<Song[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  useEffect(() => {
    listSongs({ favorite: true })
      .then(setSongs)
      .catch(() => setSongs([]))
    listCategories().then(setCategories).catch(() => setCategories([]))
  }, [])
  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 800, margin: "0 0 18px" }}>我的收藏</h1>
      <div className="song-grid">
        {songs.map((s) => (
          <SongCard
            key={s.id}
            song={s}
            onPlay={play}
            categories={categories}
            onDeleted={(id) => setSongs((cur) => cur.filter((x) => x.id !== id))}
          />
        ))}
      </div>
      {songs.length === 0 && <p className="text-muted">还没有收藏</p>}
    </div>
  )
}
