"use client"
import { useEffect, useState } from "react"
import { takeReuse } from "@/lib/reuse"
import { generate, getJob } from "@/lib/api"
import { usePlayer } from "@/lib/player"
import AdvancedSettings, { type AdvValue } from "./AdvancedSettings"
import type { GenerateInput, Job } from "@/lib/types"
import { useStyles } from "@/lib/styles"
import { formatEta } from "@/lib/format"

type Status = "idle" | "queued" | "running" | "error"

export default function GenerateForm() {
  const { play } = usePlayer()
  const styles = useStyles()
  const [title, setTitle] = useState("")
  const [lyrics, setLyrics] = useState("")
  const [feeling, setFeeling] = useState("")
  const [instrumental, setInstrumental] = useState(false)
  const [count, setCount] = useState<1 | 2>(1)
  const [adv, setAdv] = useState<AdvValue>({
    mood: [],
    vocal_gender: "",
    language: "",
    preset: "",
    vocal_timbre: "",
    creativity: "normal",
  })
  // 从歌曲卡片「复用设置」跳过来:预填一次就清掉
  useEffect(() => {
    const d = takeReuse()
    if (!d) return
    setLyrics(d.lyrics)
    setFeeling(d.feeling)
    setInstrumental(d.instrumental)
    setAdv((s) => ({ ...s, ...d.adv }))
  }, [])
  const [status, setStatus] = useState<Status>("idle")
  const [msg, setMsg] = useState("")

  /** 一个任务当前状态的一句话描述 */
  function describe(job: Job, startedAt: number): string {
    const eta = formatEta(job.eta_seconds)
    if (job.status === "queued") {
      const ahead = Math.max(0, (job.position ?? 1) - 1)
      const wait = eta ? ` · 预计${eta}后完成` : ""
      return ahead > 0 ? `排队中 · 前面还有 ${ahead} 首${wait}` : `排队中 · 即将开始${wait}`
    }
    if (job.stage) {
      const pct = Math.round((job.progress ?? 0) * 100)
      return `${job.stage} ${pct}%${eta ? ` · ${eta}` : ""}`
    }
    return `生成中… ${Math.round((Date.now() - startedAt) / 1000)}s`
  }

  /** 跟踪一个或多个(两版对比)任务直到全部结束;完成后播放第一首出来的歌 */
  async function poll(jobIds: string[], startedAt: number) {
    const labels = jobIds.length > 1 ? jobIds.map((_, i) => `版本 ${"AB"[i]} · `) : [""]
    for (;;) {
      const jobs = await Promise.all(jobIds.map((id) => getJob(id)))
      const pending = jobs.findIndex((j) => j.status === "queued" || j.status === "running")
      if (pending === -1) {
        const firstSong = jobs.find((j) => j.status === "done" && j.song)?.song
        if (firstSong) play(firstSong)
        const failed = jobs.findIndex((j) => j.status === "error")
        if (failed === -1) {
          setStatus("idle")
        } else {
          setStatus("error")
          setMsg(`${labels[failed]}${jobs[failed].error || "生成失败"}`)
        }
        return
      }
      setStatus(jobs[pending].status as Status)
      setMsg(labels[pending] + describe(jobs[pending], startedAt))
      await new Promise((r) => setTimeout(r, 2500))
    }
  }

  async function onSubmit() {
    const startedAt = Date.now()
    setStatus("queued")
    setMsg("提交中…")
    const input: GenerateInput = {
      lyrics,
      title: title.trim(),
      feeling,
      length: "auto", // 时长按歌词自动估算,不再让用户手动选挡位
      seed: null,
      instrumental,
      count,
      overrides: {
        preset: adv.preset,
        mood: adv.mood,
        vocal_gender: adv.vocal_gender,
        language: adv.language,
        vocal_timbre: adv.vocal_timbre,
        creativity: adv.creativity,
      },
    }
    try {
      const { job_id, job_ids } = await generate(input)
      await poll(job_ids?.length ? job_ids : [job_id], startedAt)
    } catch (e) {
      setStatus("error")
      setMsg(e instanceof Error ? e.message : "提交失败")
    }
  }

  const busy = status === "queued" || status === "running"
  return (
    <div className="gen-form">
      <div className="bg-panel gen-lyrics" style={{ padding: 16, borderRadius: 14 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h4 style={{ marginTop: 0, fontSize: 14 }}>歌词</h4>
          <label style={{ fontSize: 12, color: "var(--muted)", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={instrumental}
              onChange={(e) => setInstrumental(e.target.checked)}
              style={{ marginRight: 4 }}
            />
            纯音乐（无人声）
          </label>
        </div>
        <textarea
          value={lyrics}
          onChange={(e) => setLyrics(e.target.value)}
          disabled={instrumental}
          placeholder={instrumental ? "纯音乐无需歌词" : "[Verse]\n我曾走过那条街……"}
          rows={10}
          style={{
            width: "100%",
            background: "var(--field)",
            color: "var(--ink)",
            border: "1px solid var(--line)",
            borderRadius: 10,
            padding: 12,
          }}
        />
      </div>
      <div className="bg-panel gen-settings" style={{ padding: 16, borderRadius: 14 }}>
        <h4 style={{ marginTop: 0, fontSize: 14 }}>歌名（可选）</h4>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="不填则自动命名"
          maxLength={20}
          style={{
            width: "100%",
            background: "var(--field)",
            color: "var(--ink)",
            border: "1px solid var(--brand)",
            borderRadius: 10,
            padding: 10,
            marginBottom: 14,
          }}
        />
        <h4 style={{ marginTop: 0, fontSize: 14 }}>想要什么感觉</h4>
        <input
          value={feeling}
          onChange={(e) => setFeeling(e.target.value)}
          placeholder="女声，R&B，深夜，温柔"
          style={{
            width: "100%",
            background: "var(--field)",
            color: "var(--ink)",
            border: "1px solid var(--brand)",
            borderRadius: 10,
            padding: 10,
            marginBottom: 14,
          }}
        />
        <AdvancedSettings styles={styles} value={adv} onChange={(patch) => setAdv((s) => ({ ...s, ...patch }))} />
        <p className="text-muted" style={{ fontSize: 12 }}>
          版本
        </p>
        <div style={{ display: "flex", gap: 7 }}>
          {([1, 2] as const).map((n) => (
            <span
              key={n}
              role="button"
              aria-pressed={count === n}
              onClick={() => setCount(n)}
              style={{
                padding: "6px 12px",
                borderRadius: 8,
                cursor: "pointer",
                fontSize: 12,
                border: count === n ? "1px solid var(--brand)" : "1px solid var(--line)",
                background: count === n ? "rgba(47,107,216,.16)" : "rgba(255,255,255,.55)",
                color: count === n ? "var(--brand)" : "var(--muted)",
              }}
            >
              {n === 1 ? "1 首" : "2 首对比"}
            </span>
          ))}
        </div>
        <button
          className="glow-btn"
          onClick={onSubmit}
          disabled={busy}
          style={{
            width: "100%",
            marginTop: 16,
            padding: 14,
            border: "none",
            borderRadius: 12,
            color: "#fff",
            fontWeight: 800,
            fontSize: 15,
            cursor: busy ? "not-allowed" : "pointer",
            opacity: busy ? 0.7 : 1,
          }}
        >
          {busy ? msg : "✦ 生成我的歌曲"}
        </button>
        {status === "error" && (
          <p style={{ color: "var(--danger)", fontSize: 12, marginTop: 8 }}>{msg}</p>
        )}
      </div>
    </div>
  )
}
