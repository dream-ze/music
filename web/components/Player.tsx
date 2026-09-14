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
        background: "rgba(255,255,255,.62)",
        backdropFilter: "blur(18px) saturate(1.1)",
        WebkitBackdropFilter: "blur(18px) saturate(1.1)",
        borderTop: "1px solid rgba(255,255,255,.6)",
      }}
    >
      <div
        style={{
          width: 34,
          height: 34,
          borderRadius: 7,
          background: "linear-gradient(135deg,#2f6bd8,#8fd0f5)",
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
