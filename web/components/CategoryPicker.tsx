"use client"
import { useState, useEffect } from "react"
import { createPortal } from "react-dom"
import { createCategory } from "@/lib/api"
import type { Category } from "@/lib/types"

/**
 * "添加到分类"底部弹层,跟网易云"收藏到歌单"一个思路:打勾多选,
 * 互不排斥;还能直接在这里新建分类,不用再跑去侧栏(手机上侧栏本来就看不到)。
 */
export default function CategoryPicker({
  categories,
  selectedIds,
  onToggle,
  onClose,
  onCategoriesChanged,
}: {
  categories: Category[]
  selectedIds: string[]
  onToggle: (categoryId: string) => void
  onClose: () => void
  /** 新建分类成功后回调,调用方借机刷新分类列表(含新的这一条) */
  onCategoriesChanged?: () => void
}) {
  const [newName, setNewName] = useState("")
  const [creating, setCreating] = useState(false)
  // 卡片有 backdrop-filter,会给 position:fixed 的子元素另开一个定位基准,
  // 面板会被缩在卡片那个小方框里而不是铺满屏幕;传送到 body 上才能真正全屏。
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  async function handleCreate() {
    const name = newName.trim()
    if (!name || creating) return
    setCreating(true)
    try {
      await createCategory(name)
      setNewName("")
      onCategoriesChanged?.()
    } catch {
      // 新建失败不用特别提示,输入框内容留着,用户可以重试
    } finally {
      setCreating(false)
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
          maxWidth: 380,
          borderRadius: "16px 16px 0 0",
          padding: "14px 18px 20px",
          maxHeight: "60vh",
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
          <span style={{ fontWeight: 700, fontSize: 14 }}>添加到分类</span>
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

        {categories.length === 0 && (
          <p className="text-muted" style={{ fontSize: 12.5, margin: "0 0 10px" }}>
            还没有分类,先新建一个吧
          </p>
        )}

        {categories.map((c) => (
          <label
            key={c.id}
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
              checked={selectedIds.includes(c.id)}
              onChange={() => onToggle(c.id)}
            />
            <span style={{ flex: 1 }}>{c.name}</span>
            <span className="text-muted" style={{ fontSize: 11 }}>
              {c.song_count}
            </span>
          </label>
        ))}

        <div style={{ display: "flex", gap: 6, marginTop: 12 }}>
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleCreate()
            }}
            placeholder="+ 新建分类"
            maxLength={20}
            style={{
              flex: 1,
              fontSize: 13,
              padding: "8px 10px",
              borderRadius: 8,
              border: "1px solid var(--line)",
              background: "var(--field)",
              color: "var(--ink)",
            }}
          />
          <button
            onClick={handleCreate}
            disabled={creating || !newName.trim()}
            style={{
              border: "none",
              borderRadius: 8,
              padding: "0 14px",
              fontSize: 13,
              fontWeight: 600,
              cursor: creating || !newName.trim() ? "not-allowed" : "pointer",
              opacity: creating || !newName.trim() ? 0.5 : 1,
              background: "rgba(47,107,216,.16)",
              color: "var(--brand)",
            }}
          >
            确定
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}
