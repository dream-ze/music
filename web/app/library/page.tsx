"use client"
import { useEffect, useState } from "react"
import { listSongs } from "@/lib/api"
import SongCard from "@/components/SongCard"
import { usePlayer } from "@/lib/player"
import type { Song } from "@/lib/types"

export default function Library() {
  const { play } = usePlayer()
  const [songs, setSongs] = useState<Song[]>([])
  const [q, setQ] = useState("")
  const [tab, setTab] = useState<"all" | "fav">("all")

  useEffect(() => {
    listSongs({ q, favorite: tab === "fav" })
      .then(setSongs)
      .catch(() => setSongs([]))
  }, [q, tab])

  const tabStyle = (on: boolean) =>
    ({
      padding: "8px 14px",
      borderRadius: 8,
      border: "none",
      cursor: "pointer",
      background: on ? "rgba(176,107,255,.16)" : "rgba(255,255,255,.05)",
      color: on ? "#fff" : "var(--muted)",
    }) as const

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 800, margin: "0 0 4px" }}>作品库</h1>
      <p className="text-muted" style={{ margin: "0 0 18px" }}>
        大家用 AI 创作的所有歌曲
      </p>
      <div style={{ display: "flex", gap: 12, marginBottom: 18 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="🔍 搜索歌名、风格、歌词"
          style={{
            flex: 1,
            background: "var(--panel)",
            color: "var(--ink)",
            border: "1px solid var(--line)",
            borderRadius: 9,
            padding: "9px 13px",
          }}
        />
        <button onClick={() => setTab("all")} style={tabStyle(tab === "all")}>
          全部
        </button>
        <button onClick={() => setTab("fav")} style={tabStyle(tab === "fav")}>
          我的收藏
        </button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14 }}>
        {songs.map((s) => (
          <SongCard key={s.id} song={s} onPlay={play} />
        ))}
      </div>
      {songs.length === 0 && <p className="text-muted">还没有歌曲</p>}
    </div>
  )
}
