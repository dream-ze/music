"use client"
import type { ActiveJob } from "@/lib/types"

/** 作品库里"还在生成"的占位卡片:和 SongCard 同尺寸,没有播放/收藏。 */
export default function PendingCard({ job }: { job: ActiveJob }) {
  const running = job.status === "running"
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
        {running ? "生成中…" : "排队中…"}
      </div>
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
          <span>--:--</span>
        </div>
      </div>
    </div>
  )
}
