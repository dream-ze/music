"use client"
import Link from "next/link"
import { Suspense, useEffect, useState } from "react"
import { usePathname, useSearchParams, useRouter } from "next/navigation"
import { listCategories, createCategory, deleteCategory, addSongToCategory } from "@/lib/api"
import { UNCATEGORIZED, SONG_DRAG_MIME, type Category } from "@/lib/types"

const items = [
  { href: "/", label: "✦ 创作" },
  { href: "/library", label: "▤ 作品库" },
  { href: "/favorites", label: "♡ 我的收藏" },
]

// 静态导出下 useSearchParams 必须包 Suspense,否则整页无法预渲染;
// 外层默认导出保持无参数,布局那边不用为此改代码。
export default function Sidebar() {
  return (
    <Suspense fallback={<SidebarShell />}>
      <SidebarContent />
    </Suspense>
  )
}

function SidebarShell() {
  return (
    <aside
      className="app-sidebar"
      style={{
        width: 170,
        padding: "18px 12px",
        borderRight: "1px solid rgba(255,255,255,.5)",
        background: "rgba(255,255,255,.42)",
      }}
    />
  )
}

function SidebarContent() {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const router = useRouter()
  const activeCat = pathname === "/library" ? searchParams.get("cat") : null

  const [categories, setCategories] = useState<Category[]>([])
  const [newName, setNewName] = useState("")
  const [dragOver, setDragOver] = useState<string | null>(null)

  const load = () => listCategories().then(setCategories).catch(() => {})
  useEffect(() => {
    load()
    // 歌曲卡片上的归类下拉框会直接改后端,侧栏这边不知道;定时刷新一下计数,
    // 不用为这一个小数字搭一套跨组件通知
    const timer = setInterval(load, 8000)
    return () => clearInterval(timer)
  }, [])

  function goToCategory(cat: string | null) {
    router.push(cat ? `/library?cat=${encodeURIComponent(cat)}` : "/library")
  }

  async function handleCreate() {
    const name = newName.trim()
    if (!name) return
    setNewName("")
    try {
      await createCategory(name)
      load()
    } catch {
      // 静默失败:分类是辅助功能,报错不值得打断用户
    }
  }

  async function handleDeleteCategory(id: string, name: string) {
    if (
      !window.confirm(`删除分类《${name}》？这个分类下的歌不会被删，只会变回未分类。`)
    )
      return
    try {
      await deleteCategory(id)
      if (activeCat === id) goToCategory(null)
      load()
    } catch {
      // 同上
    }
  }

  function handleDrop(e: React.DragEvent, catId: string) {
    e.preventDefault()
    setDragOver(null)
    const songId = e.dataTransfer.getData(SONG_DRAG_MIME)
    if (!songId) return
    // 拖过去 = 加进这个分类,不会把歌从其他分类里挪走(一首歌能同时属于好几个)
    addSongToCategory(songId, catId)
      .then(load)
      .catch(() => {})
  }

  const rowBase = {
    display: "block",
    padding: "9px 12px",
    borderRadius: 9,
    cursor: "pointer",
    fontSize: 13,
    marginBottom: 2,
  } as const

  const rowStyle = (key: string, isActive: boolean) => ({
    ...rowBase,
    background:
      dragOver === key
        ? "rgba(47,107,216,.22)"
        : isActive
          ? "rgba(47,107,216,.16)"
          : "transparent",
    outline: dragOver === key ? "1px dashed var(--brand)" : "none",
    color: isActive ? "var(--brand)" : "var(--muted)",
  })

  return (
    <aside
      className="app-sidebar"
      style={{
        width: 170,
        padding: "18px 12px",
        borderRight: "1px solid rgba(255,255,255,.5)",
        background: "rgba(255,255,255,.42)",
        backdropFilter: "blur(16px) saturate(1.1)",
        WebkitBackdropFilter: "blur(16px) saturate(1.1)",
      }}
    >
      {items.map((it) => (
        <Link
          key={it.href}
          href={it.href}
          className="text-muted"
          style={{
            display: "block",
            padding: "10px 12px",
            borderRadius: 9,
            textDecoration: "none",
            marginBottom: 4,
          }}
        >
          {it.label}
        </Link>
      ))}

      <div
        style={{ borderTop: "1px solid var(--line)", margin: "12px 0 8px" }}
      />
      <p
        className="text-muted"
        style={{ fontSize: 11, padding: "0 12px", margin: "0 0 4px" }}
      >
        分类 · 把歌拖到这里
      </p>

      {/* 未分类只用来筛选,不接收拖拽——一首歌能同时在好几个分类里,
          "拖到未分类"已经没有唯一确定的含义(退出哪一个?全部退出?) */}
      <div
        role="button"
        onClick={() => goToCategory(UNCATEGORIZED)}
        style={rowStyle(UNCATEGORIZED, activeCat === UNCATEGORIZED)}
      >
        未分类
      </div>

      {categories.map((c) => (
        <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 2 }}>
          <div
            role="button"
            onClick={() => goToCategory(c.id)}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(c.id)
            }}
            onDragLeave={() => setDragOver(null)}
            onDrop={(e) => handleDrop(e, c.id)}
            style={{ ...rowStyle(c.id, activeCat === c.id), flex: 1, overflow: "hidden" }}
          >
            <span
              style={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                display: "inline-block",
                maxWidth: "80%",
                verticalAlign: "bottom",
              }}
            >
              {c.name}
            </span>{" "}
            <span style={{ fontSize: 10.5, opacity: 0.7 }}>{c.song_count}</span>
          </div>
          <button
            aria-label="删除分类"
            onClick={() => handleDeleteCategory(c.id, c.name)}
            title="删除分类"
            style={{
              border: "none",
              background: "none",
              color: "var(--muted)",
              cursor: "pointer",
              fontSize: 13,
              padding: "2px 6px",
            }}
          >
            ×
          </button>
        </div>
      ))}

      <div style={{ padding: "6px 4px 0" }}>
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleCreate()
          }}
          placeholder="+ 新建分类"
          maxLength={20}
          style={{
            width: "100%",
            fontSize: 12,
            padding: "7px 9px",
            borderRadius: 8,
            border: "1px solid var(--line)",
            background: "var(--field)",
            color: "var(--ink)",
          }}
        />
      </div>
    </aside>
  )
}
