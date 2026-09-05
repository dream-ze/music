"use client"

const GENRES = ["流行", "民谣", "摇滚", "R&B", "电子", "古典"]
const MOODS = ["温柔", "悲伤", "治愈", "浪漫", "欢乐"]

export interface AdvValue {
  genre: string[]
  mood: string[]
  vocal_gender: string
  language: string
  length: string
  seed: string
}

export default function AdvancedSettings({
  value,
  onChange,
}: {
  value: AdvValue
  onChange: (patch: Partial<AdvValue>) => void
}) {
  const chip = (on: boolean) =>
    ({
      padding: "6px 12px",
      borderRadius: 8,
      cursor: "pointer",
      fontSize: 12,
      border: on ? "1px solid var(--brand)" : "1px solid var(--line)",
      background: on ? "rgba(176,107,255,.16)" : "rgba(255,255,255,.05)",
      color: on ? "#fff" : "var(--muted)",
    }) as const
  const toggle = (arr: string[], v: string) =>
    arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]

  return (
    <div>
      <p className="text-muted" style={{ fontSize: 12 }}>
        风格
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 12 }}>
        {GENRES.map((g) => (
          <span
            key={g}
            style={chip(value.genre.includes(g))}
            onClick={() => onChange({ genre: toggle(value.genre, g) })}
          >
            {g}
          </span>
        ))}
      </div>
      <p className="text-muted" style={{ fontSize: 12 }}>
        情绪
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 12 }}>
        {MOODS.map((m) => (
          <span
            key={m}
            style={chip(value.mood.includes(m))}
            onClick={() => onChange({ mood: toggle(value.mood, m) })}
          >
            {m}
          </span>
        ))}
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        <select
          value={value.vocal_gender}
          onChange={(e) => onChange({ vocal_gender: e.target.value })}
        >
          <option value="">人声(自动)</option>
          <option value="female">女声</option>
          <option value="male">男声</option>
        </select>
        <select value={value.length} onChange={(e) => onChange({ length: e.target.value })}>
          <option value="full">完整</option>
          <option value="short">短版 Demo</option>
        </select>
        <input
          placeholder="Seed(随机)"
          value={value.seed}
          onChange={(e) => onChange({ seed: e.target.value })}
          style={{ width: 90 }}
        />
      </div>
    </div>
  )
}
