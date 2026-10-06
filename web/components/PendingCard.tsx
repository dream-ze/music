"use client"
import { formatEta } from "@/lib/format"
import type { ActiveJob } from "@/lib/types"

/** 作品库里"还在生成"的占位卡片:和 SongCard 同尺寸,没有播放/收藏。 */
export default function PendingCard({ job }: { job: ActiveJob }) {
  const running = job.status === "running"
  const pct = Math.round((job.progress ?? 0) * 100)
  const label = running ? (job.stage ? `${job.stage}… ${pct}%` : "生成中…") : "排队中…"
  return (
    <div
      className="bg-panel"
      style={{ borderRadius: 12, overflow: "hidden", border: "1px dashed var(--line)" }}
    >
      <div
        className="pending-cover"
        style={{
          height: 120,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          color: "var(--brand)",
          fontSize: 13,
          fontWeight: 600,
        }}
      >
        <span className="pending-spinner" aria-hidden />
        {label}
      </div>
      {running && (
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          style={{ height: 3, background: "var(--line)" }}
        >
          <div
            style={{
              width: `${pct}%`,
              height: "100%",
              background: "var(--brand)",
              transition: "width .5s",
            }}
          />
        </div>
      )}
      <div style={{ padding: "11px 12px" }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 5 }}>{job.title}</div>
        <div className="text-muted" style={{ fontSize: 10.5, marginBottom: 7 }}>
          {job.feeling || " "}
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            color: "var(--muted)",
            fontSize: 10.5,
          }}
        >
          <span>@{job.created_by}</span>
          <span>{formatEta(job.eta_seconds) || "--:--"}</span>
        </div>
      </div>
    </div>
  )
}
