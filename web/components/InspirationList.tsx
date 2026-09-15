"use client"
import { useEffect, useState } from "react"
import { getInspirations } from "@/lib/api"
import type { Inspiration } from "@/lib/types"

export default function InspirationList({
  onPick,
}: {
  onPick: (lyrics: string, feeling: string, preset: string) => void
}) {
  const [items, setItems] = useState<Inspiration[]>([])
  useEffect(() => {
    getInspirations()
      .then(setItems)
      .catch(() => setItems([]))
  }, [])
  return (
    <div className="bg-panel" style={{ padding: 16, borderRadius: 14 }}>
      <h4 style={{ marginTop: 0, fontSize: 14 }}>灵感示例</h4>
      {items.map((it) => (
        <div
          key={it.title}
          onClick={() => onPick(it.lyrics, it.feeling, it.preset || "")}
          style={{
            padding: "9px 0",
            borderBottom: "1px solid var(--line)",
            cursor: "pointer",
          }}
        >
          <div style={{ fontSize: 12.5 }}>{it.title}</div>
          <div className="text-muted" style={{ fontSize: 10.5 }}>
            {it.feeling}
          </div>
        </div>
      ))}
    </div>
  )
}
