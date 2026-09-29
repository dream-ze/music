"use client"
import { UNCATEGORIZED, type Category } from "@/lib/types"

/**
 * 手机端分类筛选入口:侧栏在窄屏下隐藏(见 globals.css .app-sidebar),
 * 这一排横向可滑动的 chip 就是手机上唯一能按分类筛选的地方。
 * 桌面端侧栏已经有同样的功能,这里靠 CSS(.mobile-category-bar)只在
 * ≤768px 时显示,避免桌面端重复一份 UI。
 */
export default function CategoryFilterBar({
  categories,
  active,
  onSelect,
}: {
  categories: Category[]
  /** 当前 URL 上的 cat 参数;"" = 全部 */
  active: string
  onSelect: (cat: string) => void
}) {
  const chip = (on: boolean) =>
    ({
      flex: "0 0 auto",
      padding: "7px 13px",
      borderRadius: 20,
      border: "none",
      whiteSpace: "nowrap",
      fontSize: 12.5,
      cursor: "pointer",
      background: on ? "rgba(47,107,216,.16)" : "rgba(255,255,255,.65)",
      color: on ? "var(--brand)" : "var(--muted)",
    }) as const

  return (
    <div className="mobile-category-bar">
      <button onClick={() => onSelect("")} style={chip(active === "")}>
        全部
      </button>
      <button
        onClick={() => onSelect(UNCATEGORIZED)}
        style={chip(active === UNCATEGORIZED)}
      >
        未分类
      </button>
      {categories.map((c) => (
        <button key={c.id} onClick={() => onSelect(c.id)} style={chip(active === c.id)}>
          {c.name} {c.song_count}
        </button>
      ))}
    </div>
  )
}
