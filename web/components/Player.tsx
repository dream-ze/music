"use client"
import { usePlayer } from "@/lib/player"
import { formatDuration } from "@/lib/format"

export default function Player() {
  const { current } = usePlayer()
  if (!current) return null
  return (
    <div
      style={{
        position: "fixed",
        left: 0,
        right: 0,
        bottom: 0,
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "12px 22px",
        background: "#0e0b1c",
        borderTop: "1px solid var(--line)",
      }}
    >
      <div
        style={{
          width: 34,
          height: 34,
          borderRadius: 7,
          background: "linear-gradient(135deg,#7b4bff,#4b7cff)",
        }}
      />
      <div style={{ minWidth: 120 }}>
        <div style={{ fontSize: 13 }}>{current.title}</div>
        <div className="text-muted" style={{ fontSize: 11 }}>
          {formatDuration(current.duration_sec)}
        </div>
      </div>
      <audio controls autoPlay src={current.mp3_url} style={{ flex: 1, height: 34 }} />
    </div>
  )
}
