"use client"
import { useState } from "react"
import { toggleFavorite } from "@/lib/api"
import { formatDuration } from "@/lib/format"
import type { Song } from "@/lib/types"

/** 从 llm_status 里挑出回退的阶段名。字段缺失或格式坏都当作"没有降级"。 */
function degradedStages(raw: string | null | undefined): string[] {
  if (!raw) return []
  try {
    const events = JSON.parse(raw)
    if (!Array.isArray(events)) return []
    return events.filter((e) => e && e.ok === false).map((e) => String(e.stage))
  } catch {
    return []
  }
}

export default function SongCard({
  song,
  onPlay,
}: {
  song: Song
  onPlay: (s: Song) => void
}) {
  const [fav, setFav] = useState(song.favorite === 1)
  const degraded = degradedStages(song.llm_status)
  return (
    <div
      className="bg-panel"
      style={{ borderRadius: 12, overflow: "hidden", border: "1px solid var(--line)" }}
    >
      <div
        style={{
          height: 120,
          position: "relative",
          background: "linear-gradient(160deg,#8fc4ec,#dfeefb 55%,#a9c8e4)",
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
            background: "rgba(255,255,255,.72)",
            color: fav ? "#e0518c" : "#14263c",
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
            background: "rgba(255,255,255,.95)",
            color: "#14263c",
          }}
        >
          ▶
        </button>
      </div>
      <div style={{ padding: "11px 12px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginBottom: 5,
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 600 }}>{song.title}</div>
          {degraded.length > 0 && (
            <span
              title={`${degraded.join("、")}已回退，这首歌是降级生成的`}
              style={{
                fontSize: 9.5,
                padding: "1px 5px",
                borderRadius: 5,
                background: "rgba(192,57,43,.12)",
                color: "var(--danger)",
                whiteSpace: "nowrap",
              }}
            >
              降级
            </span>
          )}
        </div>
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
