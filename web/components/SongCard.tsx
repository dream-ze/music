"use client"
import { useState } from "react"
import {
  toggleFavorite,
  deleteSong,
  renameSong,
  addSongToCategory,
  removeSongFromCategory,
  generate,
} from "@/lib/api"
import { styleSummary, useStyles } from "@/lib/styles"
import { draftFromSong, saveReuse } from "@/lib/reuse"
import { useRouter } from "next/navigation"
import { formatDuration } from "@/lib/format"
import { downloadSong } from "@/lib/download"
import { usePlayer } from "@/lib/player"
import { SONG_DRAG_MIME, type Song, type Category } from "@/lib/types"
import CategoryPicker from "./CategoryPicker"

const REASON_TEXT: Record<string, string> = {
  llm_error: "模型调用失败",
  bad_json: "模型输出无法解析",
  non_english: "模型输出含中文",
  invalid_spec: "模型输出不合规",
  empty: "模型返回空响应",
  text_changed: "模型改动了歌词，已用规则断行",
  missing_genre: "模型输出缺少曲风词",
  missing_timbre: "模型输出缺少人声音色",
  conflict: "模型输出含冲突的风格词",
  unknown_genre: "未能识别曲风，已随机选择",
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
  categories = [],
  onCategoryChanged,
  onCategoriesChanged,
  onRegenerate,
}: {
  song: Song
  onPlay: (s: Song) => void
  /** 删除成功后回调,调用方从列表里移掉这张卡片 */
  onDeleted?: (id: string) => void
  /** "添加到分类"面板的选项列表 */
  categories?: Category[]
  /** 这首歌的归类变了(加入/移出某个分类)——比如正按分类筛选时,
   * 移出当前分类就该从列表里消失 */
  onCategoryChanged?: (songId: string, categoryIds: string[]) => void
  /** 面板里新建了一个分类,调用方借机刷新分类列表(含新的这一条和最新计数) */
  onCategoriesChanged?: () => void
  /** 「换一种」提交成功后回调;库页借此重新开始轮询生成中的任务 */
  onRegenerate?: () => void
}) {
  const [fav, setFav] = useState(song.favorite === 1)
  const [deleting, setDeleting] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState(false)
  const [categoryIds, setCategoryIds] = useState<string[]>(song.category_ids ?? [])
  const [pickerOpen, setPickerOpen] = useState(false)
  const [title, setTitle] = useState(song.title)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState(song.title)
  const [renaming, setRenaming] = useState(false)
  const { current, stop } = usePlayer()
  const degraded = degradedNotes(song.llm_status)
  const router = useRouter()
  const styles = useStyles()

  function handleReuse() {
    saveReuse(draftFromSong(song))
    router.push("/")
  }
  const summary = styleSummary(song.spec_json, styles)
  const [regenNote, setRegenNote] = useState("")

  async function handleRegenerate() {
    if (regenNote) return
    try {
      const spec = JSON.parse(song.spec_json)
      // 同曲风、同性别、新 seed:换一组乐器/音色/质感,而不是换成别的曲风
      await generate({
        lyrics: song.lyrics,
        title: "",
        feeling: song.feeling,
        length: "auto",
        seed: null,
        instrumental: song.instrumental === 1,
        overrides: {
          preset: spec.style_draw.preset_id,
          vocal_gender: spec.vocal?.gender || "",
        },
      })
      setRegenNote("已提交")
      onRegenerate?.()
    } catch {
      setRegenNote("提交失败")
    }
    setTimeout(() => setRegenNote(""), 2000)
  }

  async function handleDelete() {
    if (!window.confirm(`确定删除《${title}》？此操作不可恢复。`)) return
    setDeleting(true)
    try {
      await deleteSong(song.id)
      if (current?.id === song.id) stop()
      onDeleted?.(song.id)
    } catch {
      setDeleting(false)
    }
  }

  async function handleDownload() {
    if (downloading) return
    setDownloading(true)
    setDownloadError(false)
    try {
      await downloadSong(song.id, title)
    } catch {
      setDownloadError(true)
      setTimeout(() => setDownloadError(false), 2000)
    } finally {
      setDownloading(false)
    }
  }

  function startEditingTitle() {
    setTitleDraft(title)
    setEditingTitle(true)
  }

  async function handleRename() {
    const next = titleDraft.trim()
    if (!next || renaming) return
    setRenaming(true)
    try {
      const saved = await renameSong(song.id, next)
      setTitle(saved)
      setEditingTitle(false)
    } catch {
      // 保留输入框打开,让用户能改改再试一次(比如名字被截断成空)
    } finally {
      setRenaming(false)
    }
  }

  async function handleToggleCategory(categoryId: string) {
    const has = categoryIds.includes(categoryId)
    const next = has ? categoryIds.filter((id) => id !== categoryId) : [...categoryIds, categoryId]
    setCategoryIds(next)
    try {
      if (has) await removeSongFromCategory(song.id, categoryId)
      else await addSongToCategory(song.id, categoryId)
      onCategoryChanged?.(song.id, next)
    } catch {
      setCategoryIds(categoryIds)
    }
  }

  const assignedCategories = categories.filter((c) => categoryIds.includes(c.id))

  return (
    <div
      className="bg-panel"
      draggable={!deleting}
      onDragStart={(e) => e.dataTransfer.setData(SONG_DRAG_MIME, song.id)}
      style={{
        position: "relative",
        borderRadius: 12,
        overflow: "hidden",
        border: "1px solid var(--line)",
        cursor: deleting ? "default" : "grab",
      }}
    >
      {deleting && (
        // R2 删除是个真实的网络请求,快也要几百毫秒;不加这层提示,
        // 用户点了删除又看不出反应,会以为卡住了
        <div
          style={{
            position: "absolute",
            inset: 0,
            zIndex: 5,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            background: "rgba(255,255,255,.72)",
            color: "var(--muted)",
            fontSize: 12.5,
            fontWeight: 600,
          }}
        >
          <span className="pending-spinner" aria-hidden />
          删除中…
        </div>
      )}
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
        {editingTitle ? (
          <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 5 }}>
            <input
              autoFocus
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleRename()
                if (e.key === "Escape") setEditingTitle(false)
              }}
              maxLength={20}
              style={{
                flex: 1,
                minWidth: 0,
                fontSize: 13,
                fontWeight: 600,
                padding: "2px 6px",
                borderRadius: 6,
                border: "1px solid var(--brand)",
                background: "var(--field)",
                color: "var(--ink)",
              }}
            />
            <button
              aria-label="确认改名"
              onClick={handleRename}
              disabled={renaming || !titleDraft.trim()}
              style={{
                border: "none",
                background: "none",
                color: "var(--brand)",
                cursor: renaming || !titleDraft.trim() ? "not-allowed" : "pointer",
                fontSize: 13,
                padding: 2,
              }}
            >
              ✓
            </button>
            <button
              aria-label="取消改名"
              onClick={() => setEditingTitle(false)}
              style={{
                border: "none",
                background: "none",
                color: "var(--muted)",
                cursor: "pointer",
                fontSize: 13,
                padding: 2,
              }}
            >
              ×
            </button>
          </div>
        ) : (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              marginBottom: 5,
            }}
          >
            <div
              style={{
                fontSize: 13,
                fontWeight: 600,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {title}
            </div>
            <button
              aria-label="改名"
              onClick={startEditingTitle}
              title="改名"
              style={{
                border: "none",
                background: "none",
                color: "var(--muted)",
                cursor: "pointer",
                fontSize: 11,
                padding: 2,
                flex: "0 0 auto",
              }}
            >
              ✎
            </button>
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
                  flex: "0 0 auto",
                }}
              >
                降级
              </span>
            )}
          </div>
        )}
        <div className="text-muted" style={{ fontSize: 10.5, marginBottom: 7 }}>
          {song.feeling}
        </div>
        {summary && (
          <div
            style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 7 }}
          >
            <span className="text-muted" style={{ fontSize: 10.5 }}>
              {summary}
            </span>
            <button
              onClick={handleRegenerate}
              disabled={!!regenNote}
              title="同曲风换一组乐器与音色,重新生成"
              style={{
                border: "1px solid var(--line)",
                background: "rgba(255,255,255,.55)",
                color: "var(--brand)",
                borderRadius: 6,
                fontSize: 10.5,
                padding: "1px 6px",
                cursor: regenNote ? "default" : "pointer",
                flex: "0 0 auto",
              }}
            >
              {regenNote || "换一种"}
            </button>
          </div>
        )}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 4,
            marginBottom: 7,
          }}
        >
          {assignedCategories.map((c) => (
            <span
              key={c.id}
              style={{
                fontSize: 10,
                padding: "2px 7px",
                borderRadius: 10,
                background: "rgba(47,107,216,.12)",
                color: "var(--brand)",
                whiteSpace: "nowrap",
              }}
            >
              {c.name}
            </span>
          ))}
          <button
            aria-label="添加到分类"
            onClick={() => setPickerOpen(true)}
            style={{
              fontSize: 10,
              padding: "2px 7px",
              borderRadius: 10,
              border: "1px dashed var(--line)",
              background: "none",
              color: "var(--muted)",
              cursor: "pointer",
            }}
          >
            + 分类
          </button>
        </div>
        {pickerOpen && (
          <CategoryPicker
            categories={categories}
            selectedIds={categoryIds}
            onToggle={handleToggleCategory}
            onClose={() => setPickerOpen(false)}
            onCategoriesChanged={onCategoriesChanged}
          />
        )}
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
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              aria-label="复用设置"
              onClick={handleReuse}
              title="用这首歌的歌词和风格设置再写一首"
              style={{
                border: "none",
                background: "none",
                color: "var(--muted)",
                cursor: "pointer",
                fontSize: 13,
                padding: 2,
              }}
            >
              ↺
            </button>
            <button
              aria-label="下载"
              onClick={handleDownload}
              disabled={downloading}
              title={downloadError ? "下载失败,再试一次" : "下载到本地"}
              style={{
                border: "none",
                background: "none",
                color: downloadError ? "var(--danger)" : "var(--muted)",
                cursor: downloading ? "not-allowed" : "pointer",
                fontSize: 13,
                padding: 2,
                opacity: downloading ? 0.5 : 1,
              }}
            >
              {downloading ? "…" : downloadError ? "!" : "⬇"}
            </button>
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
    </div>
  )
}
