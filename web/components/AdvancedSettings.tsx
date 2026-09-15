"use client"

// 显示中文、发送英文:中文 tag 混进 caption 会削弱 ACE-Step 的条件控制(后端对中文 tag 返回 422)。
export const GENRES = [
  { label: "流行", tag: "pop" },
  { label: "民谣", tag: "folk" },
  { label: "摇滚", tag: "rock" },
  { label: "R&B", tag: "r&b" },
  { label: "电子", tag: "electronic" },
  { label: "古典", tag: "classical" },
  { label: "Hip hop", tag: "hip hop" },
]
export const MOODS = [
  { label: "温柔", tag: "gentle" },
  { label: "悲伤", tag: "sad" },
  { label: "治愈", tag: "healing" },
  { label: "浪漫", tag: "romantic" },
  { label: "欢乐", tag: "joyful" },
]
export const PRESET_OPTIONS = [
  { id: "", label: "自动" },
  { id: "hiphop.boom_bap", label: "Boom Bap" },
  { id: "hiphop.trap", label: "Trap" },
]
const HIPHOP_TAG = "hip hop"
const HIPHOP_DEFAULT_PRESET = "hiphop.boom_bap"

export interface AdvValue {
  genre: string[]
  mood: string[]
  vocal_gender: string
  language: string
  length: string
  seed: string
  preset: string
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
      background: on ? "rgba(47,107,216,.16)" : "rgba(255,255,255,.55)",
      color: on ? "var(--brand)" : "var(--muted)",
    }) as const
  const toggle = (arr: string[], v: string) =>
    arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]

  function pickGenre(tag: string) {
    const genre = toggle(value.genre, tag)
    // 选 Hip hop 且还没选 preset → 默认 boom bap(用户仍可在下方改成 Trap)
    if (tag === HIPHOP_TAG && genre.includes(tag) && !value.preset) {
      onChange({ genre, preset: HIPHOP_DEFAULT_PRESET })
    } else {
      onChange({ genre })
    }
  }

  return (
    <div>
      <p className="text-muted" style={{ fontSize: 12 }}>
        风格预设
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 12 }}>
        {PRESET_OPTIONS.map((p) => (
          <span
            key={p.id || "auto"}
            role="button"
            aria-pressed={value.preset === p.id}
            style={chip(value.preset === p.id)}
            onClick={() => onChange({ preset: p.id })}
          >
            {p.label}
          </span>
        ))}
      </div>
      <p className="text-muted" style={{ fontSize: 12 }}>
        风格
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 12 }}>
        {GENRES.map((g) => (
          <span
            key={g.tag}
            role="button"
            aria-pressed={value.genre.includes(g.tag)}
            style={chip(value.genre.includes(g.tag))}
            onClick={() => pickGenre(g.tag)}
          >
            {g.label}
          </span>
        ))}
      </div>
      <p className="text-muted" style={{ fontSize: 12 }}>
        情绪
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 12 }}>
        {MOODS.map((m) => (
          <span
            key={m.tag}
            role="button"
            aria-pressed={value.mood.includes(m.tag)}
            style={chip(value.mood.includes(m.tag))}
            onClick={() => onChange({ mood: toggle(value.mood, m.tag) })}
          >
            {m.label}
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
