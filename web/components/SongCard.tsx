"use client"
import { useState } from "react"
import { toggleFavorite } from "@/lib/api"
import { formatDuration } from "@/lib/format"
import type { Song } from "@/lib/types"

export default function SongCard({
  song,
  onPlay,
}: {
  song: Song
  onPlay: (s: Song) => void
}) {
  const [fav, setFav] = useState(song.favorite === 1)
  return (
    <div
      className="bg-panel"
      style={{ borderRadius: 12, overflow: "hidden", border: "1px solid var(--line)" }}
    >
      <div
        style={{
          height: 120,
          position: "relative",
          background: "linear-gradient(135deg,#7b4bff,#4b7cff)",
        }}
      >
        <button
          aria-label="收藏"
          onClick={() => toggleFavorite(song.id).then(setFav).catch(() => {})}
          style={{
            position: "absolute",
            top: 9,
            right: 9,
            border: "none",
            width: 24,
            height: 24,
            borderRadius: "50%",
            cursor: "pointer",
            background: "rgba(0,0,0,.35)",
            color: fav ? "#ff7ac0" : "#fff",
          }}
        >
          {fav ? "♥" : "♡"}
        </button>
        <button
          aria-label="播放"
          onClick={() => onPlay(song)}
          style={{
            position: "absolute",
            bottom: 10,
            right: 10,
            border: "none",
            width: 34,
            height: 34,
            borderRadius: "50%",
            cursor: "pointer",
            background: "rgba(255,255,255,.92)",
            color: "#3a1a6b",
          }}
        >
          ▶
        </button>
      </div>
      <div style={{ padding: "11px 12px" }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 5 }}>{song.title}</div>
        <div className="text-muted" style={{ fontSize: 10.5, marginBottom: 7 }}>
          {song.feeling}
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            color: "var(--muted)",
            fontSize: 10.5,
          }}
        >
          <span>@{song.created_by}</span>
          <span>{formatDuration(song.duration_sec)}</span>
        </div>
      </div>
    </div>
  )
}
