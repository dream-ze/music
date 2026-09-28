"use client"
import { useState } from "react"
import { toggleFavorite, deleteSong } from "@/lib/api"
import { formatDuration } from "@/lib/format"
import { usePlayer } from "@/lib/player"
import type { Song } from "@/lib/types"

const REASON_TEXT: Record<string, string> = {
  llm_error: "模型调用失败",
  bad_json: "模型输出无法解析",
  non_english: "模型输出含中文",
  invalid_spec: "模型输出不合规",
  empty: "模型返回空响应",
  text_changed: "模型改动了歌词，已用规则断行",
}

/** 从 llm_status 里挑出回退的阶段,组成「阶段：原因」说明。字段缺失或格式坏都当作"没有降级"。 */
function degradedNotes(raw: string | null | undefined): string[] {
  if (!raw) return []
  try {
    const events = JSON.parse(raw)
    if (!Array.isArray(events)) return []
    return events
      .filter((e) => e && e.ok === false)
      .map((e) => `${String(e.stage)}：${REASON_TEXT[String(e.reason)] || "已回退"}`)
  } catch {
    return []
  }
}

export default function SongCard({
  song,
  onPlay,
  onDeleted,
}: {
  song: Song
  onPlay: (s: Song) => void
  /** 删除成功后回调,调用方从列表里移掉这张卡片 */
  onDeleted?: (id: string) => void
}) {
  const [fav, setFav] = useState(song.favorite === 1)
  const [deleting, setDeleting] = useState(false)
  const { current, stop } = usePlayer()
  const degraded = degradedNotes(song.llm_status)

  async function handleDelete() {
    if (!window.confirm(`确定删除《${song.title}》？此操作不可恢复。`)) return
    setDeleting(true)
    try {
      await deleteSong(song.id)
      if (current?.id === song.id) stop()
      onDeleted?.(song.id)
    } catch {
      setDeleting(false)
    }
  }
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
              title={`${degraded.join("；")}。这首歌是降级生成的`}
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
            alignItems: "center",
            color: "var(--muted)",
            fontSize: 10.5,
          }}
        >
          <span>{formatDuration(song.duration_sec)}</span>
          <button
            aria-label="删除"
            onClick={handleDelete}
            disabled={deleting}
            title="删除这首歌"
            style={{
              border: "none",
              background: "none",
              color: "var(--muted)",
              cursor: deleting ? "not-allowed" : "pointer",
              fontSize: 13,
              padding: 2,
              opacity: deleting ? 0.5 : 1,
            }}
          >
            🗑
          </button>
        </div>
      </div>
    </div>
  )
}
