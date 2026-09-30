import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import PasscodeGate from "@/components/PasscodeGate"

beforeEach(() => {
  const store: Record<string, string> = {}
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => {
      store[k] = v
    },
    removeItem: (k: string) => {
      delete store[k]
    },
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("PasscodeGate 区分「口令错了」和「请求根本没到服务器」", () => {
  it("口令错误(接口正常返回 401)时显示「口令错误」", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }))
    render(
      <PasscodeGate>
        <div>已登录</div>
      </PasscodeGate>
    )
    await waitFor(() => screen.getByPlaceholderText("口令"))
    fireEvent.change(screen.getByPlaceholderText("口令"), { target: { value: "wrong" } })
    fireEvent.click(screen.getByText("进入"))
    await waitFor(() => expect(screen.getByText("口令错误")).toBeInTheDocument())
  })

  it("请求失败(网络/VPN 挡住之类)时显示不一样的提示,不误导成口令错了", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network fail")))
    render(
      <PasscodeGate>
        <div>已登录</div>
      </PasscodeGate>
    )
    await waitFor(() => screen.getByPlaceholderText("口令"))
    fireEvent.change(screen.getByPlaceholderText("口令"), { target: { value: "demo" } })
    fireEvent.click(screen.getByText("进入"))
    await waitFor(() => expect(screen.getByText(/连不上服务器/)).toBeInTheDocument())
    expect(screen.queryByText("口令错误")).toBeNull()
  })

  it("口令正确时放行,显示子内容", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }))
    render(
      <PasscodeGate>
        <div>已登录</div>
      </PasscodeGate>
    )
    await waitFor(() => screen.getByPlaceholderText("口令"))
    fireEvent.change(screen.getByPlaceholderText("口令"), { target: { value: "demo" } })
    fireEvent.click(screen.getByText("进入"))
    await waitFor(() => expect(screen.getByText("已登录")).toBeInTheDocument())
  })
})
