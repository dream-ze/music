import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import PendingCard from "@/components/PendingCard"

const base = { job_id: "j1", title: "冬日甜心", feeling: "女声 hip hop", created_by: "demo", created_at: "" }

describe("PendingCard", () => {
  it("生成中显示歌名/感觉/提交人,没有播放和收藏按钮", () => {
    render(<PendingCard job={{ ...base, status: "running" }} />)
    expect(screen.getByText("生成中…")).toBeInTheDocument()
    expect(screen.getByText("冬日甜心")).toBeInTheDocument()
    expect(screen.getByText("女声 hip hop")).toBeInTheDocument()
    expect(screen.getByText("@demo")).toBeInTheDocument()
    expect(screen.queryByLabelText("播放")).toBeNull()
    expect(screen.queryByLabelText("收藏")).toBeNull()
  })

  it("排队中显示排队文案", () => {
    render(<PendingCard job={{ ...base, status: "queued" }} />)
    expect(screen.getByText("排队中…")).toBeInTheDocument()
  })
})
