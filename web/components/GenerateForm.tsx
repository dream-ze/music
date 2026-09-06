"use client"
import { useState } from "react"
import { generate, getJob } from "@/lib/api"
import { usePlayer } from "@/lib/player"
import AdvancedSettings, { type AdvValue } from "./AdvancedSettings"
import InspirationList from "./InspirationList"
import type { GenerateInput } from "@/lib/types"

type Status = "idle" | "queued" | "running" | "error"

export default function GenerateForm() {
  const { play } = usePlayer()
  const [lyrics, setLyrics] = useState("")
  const [feeling, setFeeling] = useState("")
  const [adv, setAdv] = useState<AdvValue>({
    genre: [],
    mood: [],
    vocal_gender: "",
    language: "",
    length: "full",
    seed: "",
  })
  const [status, setStatus] = useState<Status>("idle")
  const [msg, setMsg] = useState("")

  async function poll(jobId: string, startedAt: number) {
    for (;;) {
      const job = await getJob(jobId)
      if (job.status === "done") {
        if (job.song) play(job.song)
        setStatus("idle")
        return
      }
      if (job.status === "error") {
        setStatus("error")
        setMsg(job.error || "生成失败")
        return
      }
      setStatus(job.status)
      if (job.status === "queued") {
        const ahead = Math.max(0, (job.position ?? 1) - 1)
        setMsg(ahead > 0 ? `排队中 · 前面还有 ${ahead} 首（每首约 2-4 分钟）` : "排队中 · 即将开始…")
      } else {
        const elapsed = Math.round((Date.now() - startedAt) / 1000)
        setMsg(`生成中… ${elapsed}s · Mac 出歌约 2-4 分钟，请耐心`)
      }
      await new Promise((r) => setTimeout(r, 2500))
    }
  }

  async function onSubmit() {
    const startedAt = Date.now()
    setStatus("queued")
    setMsg("提交中…")
    const input: GenerateInput = {
      lyrics,
      feeling,
      length: adv.length as "full" | "short",
      seed: adv.seed ? Number(adv.seed) : null,
      instrumental: false,
      overrides: {
        genre: adv.genre,
        mood: adv.mood,
        vocal_gender: adv.vocal_gender,
        language: adv.language,
      },
    }
    try {
      const { job_id } = await generate(input)
      await poll(job_id, startedAt)
    } catch (e) {
      setStatus("error")
      setMsg(e instanceof Error ? e.message : "提交失败")
    }
  }

  const busy = status === "queued" || status === "running"
  return (
    <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
      <div className="bg-panel" style={{ flex: 1.3, padding: 16, borderRadius: 14 }}>
        <h4 style={{ marginTop: 0, fontSize: 14 }}>歌词</h4>
        <textarea
          value={lyrics}
          onChange={(e) => setLyrics(e.target.value)}
          placeholder={"[Verse]\n我曾走过那条街……"}
          rows={10}
          style={{
            width: "100%",
            background: "var(--bg)",
            color: "var(--ink)",
            border: "1px solid var(--line)",
            borderRadius: 10,
            padding: 12,
          }}
        />
      </div>
      <div className="bg-panel" style={{ flex: 1.1, padding: 16, borderRadius: 14 }}>
        <h4 style={{ marginTop: 0, fontSize: 14 }}>想要什么感觉</h4>
        <input
          value={feeling}
          onChange={(e) => setFeeling(e.target.value)}
          placeholder="女声，R&B，深夜，温柔"
          style={{
            width: "100%",
            background: "var(--bg)",
            color: "var(--ink)",
            border: "1px solid var(--brand)",
            borderRadius: 10,
            padding: 10,
            marginBottom: 14,
          }}
        />
        <AdvancedSettings value={adv} onChange={(patch) => setAdv((s) => ({ ...s, ...patch }))} />
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
          <p style={{ color: "#ff7a8a", fontSize: 12, marginTop: 8 }}>{msg}</p>
        )}
      </div>
      <div style={{ flex: 0.85 }}>
        <InspirationList
          onPick={(l, f) => {
            setLyrics(l)
            setFeeling(f)
          }}
        />
      </div>
    </div>
  )
}
