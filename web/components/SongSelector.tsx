"use client"
import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { listSongs, addSongToCategory, removeSongFromCategory } from "@/lib/api"
import type { Song } from "@/lib/types"

/**
 * 打开一个分类,从全部歌曲里勾选加进来——跟网易云打开歌单点"添加歌曲"
 * 是同一个思路,跟 CategoryPicker(从一首歌出发选分类)刚好反过来,
 * 这里是从分类出发选歌曲。
 */
export default function SongSelector({
  categoryId,
  categoryName,
  onClose,
  onChanged,
}: {
  categoryId: string
  categoryName: string
  onClose: () => void
  /** 有歌曲加入/移出时回调,调用方借机刷新当前的分类筛选列表和计数 */
  onChanged?: () => void
}) {
  const [songs, setSongs] = useState<Song[]>([])
  const [loading, setLoading] = useState(true)
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  useEffect(() => {
    listSongs({})
      .then((s) => {
        setSongs(s)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  async function toggle(song: Song) {
    const has = (song.category_ids ?? []).includes(categoryId)
    setSongs((cur) =>
      cur.map((s) =>
        s.id === song.id
          ? {
              ...s,
              category_ids: has
                ? (s.category_ids ?? []).filter((id) => id !== categoryId)
                : [...(s.category_ids ?? []), categoryId],
            }
          : s
      )
    )
    try {
      if (has) await removeSongFromCategory(song.id, categoryId)
      else await addSongToCategory(song.id, categoryId)
      onChanged?.()
    } catch {
      setSongs((cur) => cur.map((s) => (s.id === song.id ? song : s)))
    }
  }

  if (!mounted) return null

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        background: "rgba(20,38,60,.32)",
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
      }}
    >
      <div
        className="bg-panel"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 420,
          borderRadius: "16px 16px 0 0",
          padding: "14px 18px 20px",
          maxHeight: "70vh",
          overflowY: "auto",
          background: "rgba(255,255,255,.96)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 10,
          }}
        >
          <span style={{ fontWeight: 700, fontSize: 14 }}>选择歌曲 · {categoryName}</span>
          <button
            aria-label="关闭"
            onClick={onClose}
            style={{
              border: "none",
              background: "none",
              color: "var(--muted)",
              cursor: "pointer",
              fontSize: 18,
              lineHeight: 1,
              padding: 2,
            }}
          >
            ×
          </button>
        </div>

        {loading && (
          <p className="text-muted" style={{ fontSize: 12.5 }}>
            加载中…
          </p>
        )}
        {!loading && songs.length === 0 && (
          <p className="text-muted" style={{ fontSize: 12.5 }}>
            还没有歌曲
          </p>
        )}

        {songs.map((s) => (
          <label
            key={s.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 9,
              padding: "8px 2px",
              fontSize: 13.5,
              cursor: "pointer",
              borderBottom: "1px solid var(--line)",
            }}
          >
            <input
              type="checkbox"
              checked={(s.category_ids ?? []).includes(categoryId)}
              onChange={() => toggle(s)}
            />
            <span
              style={{
                flex: 1,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {s.title}
            </span>
            <span
              className="text-muted"
              style={{
                fontSize: 11,
                maxWidth: 120,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {s.feeling}
            </span>
          </label>
        ))}
      </div>
    </div>,
    document.body
  )
}
