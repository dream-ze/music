"use client"
import Link from "next/link"
import { usePlayer } from "@/lib/player"
import { formatDuration } from "@/lib/format"

export default function Player() {
  const { current } = usePlayer()
  if (!current) return null
  return (
    <div
      className="player-bar"
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
      <div style={{ minWidth: 0, maxWidth: 260 }}>
        <div style={{ fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {current.title}
        </div>
        <div className="text-muted" style={{ fontSize: 11 }}>
          {formatDuration(current.duration_sec)}
        </div>
      </div>
      {/* 歌词是独立的一整页(像网易云那样),不是弹出的小面板;
          Player 是全局挂在 layout 里的,跳过去之后播放不会断 */}
      <Link
        href="/now-playing"
        aria-label="查看歌词"
        style={{
          border: "none",
          borderRadius: 8,
          padding: "6px 11px",
          fontSize: 12,
          fontWeight: 600,
          color: "var(--muted)",
          textDecoration: "none",
        }}
      >
        词
      </Link>
      <audio controls autoPlay src={current.mp3_url} className="player-audio" />
    </div>
  )
}
