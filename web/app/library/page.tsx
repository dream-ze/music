"use client"
import { Suspense, useCallback, useEffect, useRef, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { listSongs, listActiveJobs, listCategories } from "@/lib/api"
import SongCard from "@/components/SongCard"
import PendingCard from "@/components/PendingCard"
import { usePlayer } from "@/lib/player"
import { UNCATEGORIZED, type Song, type ActiveJob, type Category } from "@/lib/types"

const POLL_MS = 5000

// 静态导出下 useSearchParams 必须包 Suspense,否则整页无法预渲染
export default function Library() {
  return (
    <Suspense fallback={null}>
      <LibraryContent />
    </Suspense>
  )
}

function LibraryContent() {
  const { play } = usePlayer()
  const router = useRouter()
  const searchParams = useSearchParams()
  const cat = searchParams.get("cat") || ""

  const [songs, setSongs] = useState<Song[]>([])
  const [jobs, setJobs] = useState<ActiveJob[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [q, setQ] = useState("")
  const [tab, setTab] = useState<"all" | "fav">("all")
  // 只在「全部」、没搜索词、也没按分类筛选时显示生成中卡片:
  // 生成中的歌还没有分类,混进筛选结果里会显得不对
  const showPending = tab === "all" && !q && !cat

  const loadSongs = useCallback(() => {
    listSongs({ q, favorite: tab === "fav", category: cat })
      .then(setSongs)
      .catch(() => setSongs([]))
  }, [q, tab, cat])

  useEffect(loadSongs, [loadSongs])
  useEffect(() => {
    listCategories().then(setCategories).catch(() => setCategories([]))
  }, [])

  // 有任务在跑就每 5 秒查一次;某个任务从列表消失 = 生成完了,重拉歌曲让它出现在原位
  const prevIds = useRef<Set<string>>(new Set())
  useEffect(() => {
    if (!showPending) {
      setJobs([])
      prevIds.current = new Set()
      return
    }
    let timer: ReturnType<typeof setTimeout> | undefined
    let cancelled = false
    const tick = async () => {
      let next: ActiveJob[] = []
      try {
        next = await listActiveJobs()
      } catch {
        next = []
      }
      if (cancelled) return
      const ids = new Set(next.map((j) => j.job_id))
      const finished = [...prevIds.current].some((id) => !ids.has(id))
      prevIds.current = ids
      setJobs(next)
      if (finished) loadSongs()
      if (next.length > 0) timer = setTimeout(tick, POLL_MS)
    }
    tick()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [showPending, loadSongs])

  const tabStyle = (on: boolean) =>
    ({
      padding: "8px 14px",
      borderRadius: 8,
      border: "none",
      cursor: "pointer",
      background: on ? "rgba(47,107,216,.16)" : "rgba(255,255,255,.55)",
      color: on ? "var(--brand)" : "var(--muted)",
    }) as const

  const activeCategoryName =
    cat === UNCATEGORIZED
      ? "未分类"
      : categories.find((c) => c.id === cat)?.name

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 800, margin: "0 0 4px" }}>作品库</h1>
      <p className="text-muted" style={{ margin: "0 0 18px" }}>
        {activeCategoryName ? (
          <>
            分类：{activeCategoryName}{" "}
            <span
              role="button"
              onClick={() => router.push("/library")}
              style={{ color: "var(--brand)", cursor: "pointer" }}
            >
              · 返回全部
            </span>
          </>
        ) : (
          "大家用 AI 创作的所有歌曲"
        )}
      </p>
      <div className="search-row">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="🔍 搜索歌名、风格、歌词"
          style={{
            background: "var(--field)",
            color: "var(--ink)",
            border: "1px solid var(--line)",
            borderRadius: 9,
            padding: "9px 13px",
          }}
        />
        <button onClick={() => setTab("all")} style={tabStyle(tab === "all")}>
          全部
        </button>
        <button onClick={() => setTab("fav")} style={tabStyle(tab === "fav")}>
          我的收藏
        </button>
      </div>
      <div className="song-grid">
        {jobs.map((j) => (
          <PendingCard key={j.job_id} job={j} />
        ))}
        {songs.map((s) => (
          <SongCard
            key={s.id}
            song={s}
            onPlay={play}
            categories={categories}
            onDeleted={(id) => setSongs((cur) => cur.filter((x) => x.id !== id))}
            onCategoryChanged={(id, newCat) => {
              // 正按分类筛选时,挪去别的分类(或挪出/挪入未分类)的歌要从当前列表里消失
              const newKey = newCat || UNCATEGORIZED
              if (cat && newKey !== cat) {
                setSongs((cur) => cur.filter((x) => x.id !== id))
              }
              listCategories().then(setCategories).catch(() => {})
            }}
          />
        ))}
      </div>
      {songs.length === 0 && jobs.length === 0 && <p className="text-muted">还没有歌曲</p>}
    </div>
  )
}
