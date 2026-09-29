"use client"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { usePlayer } from "@/lib/player"

// 结构标记行,如 [Verse]、[Chorus]、[Verse - rap];当小标题处理,不当唱词
const SECTION_TAG = /^\s*\[[^\]]*\]\s*$/

export default function NowPlaying() {
  const { current } = usePlayer()
  const router = useRouter()

  if (!current) {
    return (
      <div style={{ textAlign: "center", padding: "80px 0" }}>
        <p className="text-muted" style={{ marginBottom: 12 }}>
          还没有播放的歌曲
        </p>
        <Link href="/library" style={{ color: "var(--brand)", textDecoration: "none" }}>
          去作品库看看 →
        </Link>
      </div>
    )
  }

  const lines = (current.structured_lyrics || "").split("\n")
  const hasLyrics = lines.some((l) => l.trim() && !SECTION_TAG.test(l.trim()))

  return (
    <div style={{ maxWidth: 560, margin: "0 auto" }}>
      <button
        onClick={() => router.back()}
        style={{
          border: "none",
          background: "none",
          color: "var(--muted)",
          cursor: "pointer",
          fontSize: 13,
          padding: 0,
          marginBottom: 24,
        }}
      >
        ‹ 返回
      </button>

      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <div
          style={{
            width: 180,
            height: 180,
            margin: "0 auto 16px",
            borderRadius: 20,
            background: "linear-gradient(160deg,#8fc4ec,#dfeefb 55%,#a9c8e4)",
            boxShadow: "0 16px 40px rgba(24,55,95,.18)",
          }}
        />
        <div style={{ fontSize: 20, fontWeight: 800 }}>{current.title}</div>
        <div className="text-muted" style={{ fontSize: 12.5, marginTop: 4 }}>
          {current.feeling}
        </div>
      </div>

      {hasLyrics ? (
        <div style={{ textAlign: "center" }}>
          {lines.map((line, i) => {
            const trimmed = line.trim()
            if (!trimmed) return <div key={i} style={{ height: 14 }} />
            if (SECTION_TAG.test(trimmed)) {
              return (
                <div
                  key={i}
                  className="text-muted"
                  style={{
                    fontSize: 11.5,
                    fontWeight: 700,
                    letterSpacing: 1,
                    margin: "22px 0 8px",
                  }}
                >
                  {trimmed.slice(1, -1).toUpperCase()}
                </div>
              )
            }
            return (
              <div key={i} style={{ fontSize: 16.5, lineHeight: 2, color: "var(--ink)" }}>
                {trimmed}
              </div>
            )
          })}
        </div>
      ) : (
        <p className="text-muted" style={{ textAlign: "center" }}>
          暂无歌词
        </p>
      )}
    </div>
  )
}
