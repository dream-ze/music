"use client"

// 结构标记行,如 [Verse]、[Chorus]、[Verse - rap];当小标题处理,不当唱词
const SECTION_TAG = /^\s*\[[^\]]*\]\s*$/

export default function LyricsPanel({
  lyrics,
  onClose,
}: {
  lyrics: string
  onClose: () => void
}) {
  const lines = lyrics.split("\n")
  return (
    <div
      className="bg-panel"
      style={{
        maxHeight: "45vh",
        overflowY: "auto",
        margin: "0 12px",
        padding: "12px 18px 18px",
        borderRadius: "14px 14px 0 0",
        borderBottom: "none",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
          position: "sticky",
          top: 0,
        }}
      >
        <span className="text-muted" style={{ fontSize: 12, fontWeight: 700 }}>
          歌词
        </span>
        <button
          aria-label="关闭歌词"
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
      {lines.map((line, i) => {
        const trimmed = line.trim()
        if (!trimmed) return <div key={i} style={{ height: 8 }} />
        if (SECTION_TAG.test(trimmed)) {
          return (
            <div
              key={i}
              className="text-muted"
              style={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: 0.5,
                margin: "12px 0 4px",
              }}
            >
              {trimmed.slice(1, -1).toUpperCase()}
            </div>
          )
        }
        return (
          <div key={i} style={{ fontSize: 14, lineHeight: 1.7 }}>
            {trimmed}
          </div>
        )
      })}
    </div>
  )
}
