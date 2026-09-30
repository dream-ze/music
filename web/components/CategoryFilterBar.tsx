"use client"
import { UNCATEGORIZED, type Category } from "@/lib/types"

/**
 * 手机端分类筛选入口:侧栏在窄屏下隐藏(见 globals.css .app-sidebar),
 * 这一排横向可滑动的 chip 就是手机上唯一能按分类筛选的地方。
 * 桌面端侧栏已经有同样的功能,这里靠 CSS(.mobile-category-bar)只在
 * ≤768px 时显示,避免桌面端重复一份 UI。
 *
 * 分类的删除入口原来只做在侧栏(桌面端),手机上没地方删——这里补上,
 * 每个分类 chip 自带一个小 ×,跟侧栏是同一套确认/调用逻辑。
 */
export default function CategoryFilterBar({
  categories,
  active,
  onSelect,
  onDelete,
}: {
  categories: Category[]
  /** 当前 URL 上的 cat 参数;"" = 全部 */
  active: string
  onSelect: (cat: string) => void
  onDelete: (categoryId: string, name: string) => void
}) {
  const chip = (on: boolean) =>
    ({
      display: "flex",
      alignItems: "center",
      flex: "0 0 auto",
      borderRadius: 20,
      whiteSpace: "nowrap",
      fontSize: 12.5,
      background: on ? "rgba(47,107,216,.16)" : "rgba(255,255,255,.65)",
      color: on ? "var(--brand)" : "var(--muted)",
    }) as const

  const plainChipButton = {
    border: "none",
    background: "none",
    color: "inherit",
    font: "inherit",
    padding: "7px 13px",
    cursor: "pointer",
  } as const

  return (
    <div className="mobile-category-bar">
      <button onClick={() => onSelect("")} style={{ ...chip(active === ""), ...plainChipButton }}>
        全部
      </button>
      <button
        onClick={() => onSelect(UNCATEGORIZED)}
        style={{ ...chip(active === UNCATEGORIZED), ...plainChipButton }}
      >
        未分类
      </button>
      {categories.map((c) => (
        <span key={c.id} style={chip(active === c.id)}>
          <button onClick={() => onSelect(c.id)} style={{ ...plainChipButton, paddingRight: 4 }}>
            {c.name} {c.song_count}
          </button>
          <button
            aria-label="删除分类"
            onClick={() => onDelete(c.id, c.name)}
            style={{ ...plainChipButton, paddingLeft: 4 }}
          >
            ×
          </button>
        </span>
      ))}
    </div>
  )
}
