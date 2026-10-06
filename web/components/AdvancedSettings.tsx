"use client"
import type { Creativity, StyleOption, Styles } from "@/lib/types"

// 显示中文、发送英文:中文 tag 混进 caption 会削弱 ACE-Step 的条件控制(后端对中文 tag 返回 422)。
export const MOODS = [
  { label: "温柔", tag: "gentle" },
  { label: "悲伤", tag: "sad" },
  { label: "治愈", tag: "healing" },
  { label: "浪漫", tag: "romantic" },
  { label: "欢乐", tag: "joyful" },
]

// 曲风分组名;后端新增 family 而这里没写时直接显示 family 原文
const FAMILY_LABEL: Record<string, string> = {
  pop: "流行",
  folk: "民谣",
  rock: "摇滚",
  rnb: "R&B",
  electronic: "电子",
  chill: "爵士 / 放松",
  cn: "中国风",
  hiphop: "说唱",
}

export interface AdvValue {
  mood: string[]
  vocal_gender: string
  language: string
  /** 曲风 id;空 = 自动(按「感觉」识别,识别不出随机) */
  preset: string
  /** 人声音色 id;空 = 按曲风自动挑 */
  vocal_timbre: string
  creativity: Creativity
}

function groupByFamily(genres: StyleOption[]): [string, StyleOption[]][] {
  const groups = new Map<string, StyleOption[]>()
  for (const g of genres) {
    const fam = g.family ?? ""
    groups.set(fam, [...(groups.get(fam) ?? []), g])
  }
  return [...groups.entries()]
}

export default function AdvancedSettings({
  value,
  onChange,
  styles,
}: {
  value: AdvValue
  onChange: (patch: Partial<AdvValue>) => void
  styles: Styles | null
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
  const row = { display: "flex", flexWrap: "wrap", gap: 7, marginBottom: 12 } as const
  const label = (text: string) => (
    <p className="text-muted" style={{ fontSize: 12 }}>
      {text}
    </p>
  )
  const loading = (
    <span className="text-muted" style={{ fontSize: 12 }}>
      加载中…
    </span>
  )
  const toggle = (arr: string[], v: string) =>
    arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]
  const option = (o: StyleOption, on: boolean, onClick: () => void) => (
    <span key={o.id} role="button" aria-pressed={on} style={chip(on)} onClick={onClick}>
      {o.label}
    </span>
  )

  return (
    <div>
      {label("曲风")}
      <div style={{ marginBottom: 12 }}>
        <div style={row}>
          <span
            role="button"
            aria-label="自动曲风"
            aria-pressed={value.preset === ""}
            style={chip(value.preset === "")}
            onClick={() => onChange({ preset: "" })}
          >
            自动
          </span>
        </div>
        {styles
          ? groupByFamily(styles.genres).map(([fam, items]) => (
              <div key={fam} style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                <span className="text-muted" style={{ fontSize: 11, minWidth: 64 }}>
                  {FAMILY_LABEL[fam] ?? fam}
                </span>
                <div style={{ ...row, marginBottom: 6 }}>
                  {items.map((g) =>
                    option(g, value.preset === g.id, () => onChange({ preset: g.id })),
                  )}
                </div>
              </div>
            ))
          : loading}
      </div>

      {label("人声音色")}
      <div style={row}>
        <span
          role="button"
          aria-label="自动音色"
          aria-pressed={value.vocal_timbre === ""}
          style={chip(value.vocal_timbre === "")}
          onClick={() => onChange({ vocal_timbre: "" })}
        >
          自动
        </span>
        {styles
          ? styles.timbres.map((t) =>
              option(t, value.vocal_timbre === t.id, () => onChange({ vocal_timbre: t.id })),
            )
          : loading}
      </div>

      {label("创意度")}
      <div style={row}>
        {styles
          ? styles.creativity.map((c) =>
              option(c, value.creativity === c.id, () =>
                onChange({ creativity: c.id as Creativity }),
              ),
            )
          : loading}
      </div>

      {label("情绪")}
      <div style={row}>
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
      <div className="opts-row">
        <select
          value={value.vocal_gender}
          onChange={(e) => onChange({ vocal_gender: e.target.value })}
        >
          <option value="">人声(自动)</option>
          <option value="female">女声</option>
          <option value="male">男声</option>
        </select>
      </div>
    </div>
  )
}
