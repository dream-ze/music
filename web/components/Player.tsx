"use client"
import { useState } from "react"
import { usePlayer } from "@/lib/player"
import { formatDuration } from "@/lib/format"
import LyricsPanel from "./LyricsPanel"

export default function Player() {
  const { current } = usePlayer()
  const [showLyrics, setShowLyrics] = useState(false)
  if (!current) return null
  const hasLyrics = !!current.structured_lyrics?.trim()
  return (
    // 歌词面板和播放条放在同一个定位容器里,面板天然贴在播放条正上方,
    // 不用管播放条实际高度(手机端会换行、高度不固定)
    <div style={{ position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 30 }}>
      {showLyrics && hasLyrics && (
        <LyricsPanel lyrics={current.structured_lyrics!} onClose={() => setShowLyrics(false)} />
      )}
      <div
        className="player-bar"
        style={{
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
        <button
          aria-label="歌词"
          onClick={() => setShowLyrics((v) => !v)}
          disabled={!hasLyrics}
          title={hasLyrics ? "查看歌词" : "暂无歌词"}
          style={{
            border: "none",
            borderRadius: 8,
            padding: "6px 11px",
            fontSize: 12,
            fontWeight: 600,
            background: showLyrics ? "rgba(47,107,216,.16)" : "transparent",
            color: showLyrics ? "var(--brand)" : "var(--muted)",
            cursor: hasLyrics ? "pointer" : "not-allowed",
            opacity: hasLyrics ? 1 : 0.4,
          }}
        >
          词
        </button>
        <audio controls autoPlay src={current.mp3_url} className="player-audio" />
      </div>
    </div>
  )
}
