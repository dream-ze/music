"use client"
import { useState, useEffect } from "react"
import { getPasscode, setPasscode } from "@/lib/passcode"

import { API_BASE as BASE } from "@/lib/api-base"

type VerifyResult = { ok: boolean; networkError?: boolean }

/** 口令错了 vs 请求根本没到服务器(网络/VPN/后端挂了),这是两码事,
 * 原来一律显示"口令错误",连不上的时候会误导人去反复改口令。 */
async function verify(passcode: string): Promise<VerifyResult> {
  try {
    const res = await fetch(`${BASE}/api/songs?limit=1`, {
      headers: { "X-Passcode": passcode },
    })
    return { ok: res.ok }
  } catch {
    return { ok: false, networkError: true }
  }
}

export default function PasscodeGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false)
  const [ok, setOk] = useState(false)
  const [val, setVal] = useState("")
  const [err, setErr] = useState("")
  const [checking, setChecking] = useState(false)

  // 首屏:若已存口令,校验一次;不通过则回到输入界面
  useEffect(() => {
    const saved = getPasscode()
    if (!saved) {
      setReady(true)
      return
    }
    verify(saved).then(({ ok: good, networkError }) => {
      setOk(good)
      if (!good) {
        setErr(
          networkError
            ? "连不上服务器,检查一下网络(比如手机开着 VPN 可能会挡住)"
            : "已保存的口令无效，请重新输入"
        )
      }
      setReady(true)
    })
  }, [])

  async function submit() {
    if (!val) return
    setChecking(true)
    setErr("")
    const { ok: good, networkError } = await verify(val)
    setChecking(false)
    if (good) {
      setPasscode(val)
      setOk(true)
    } else if (networkError) {
      setErr("连不上服务器,检查一下网络(比如手机开着 VPN 可能会挡住)")
    } else {
      setErr("口令错误")
    }
  }

  if (!ready) return null
  if (ok) return <>{children}</>

  return (
    <div
      style={{
        display: "flex",
        minHeight: "100vh",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div className="bg-panel" style={{ padding: 28, borderRadius: 14, width: 320 }}>
        <h2 style={{ marginTop: 0 }}>🎵 灵感壁炉</h2>
        <p className="text-muted" style={{ fontSize: 13 }}>
          输入口令进入
        </p>
        <input
          type="password"
          value={val}
          onChange={(e) => setVal(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit()
          }}
          placeholder="口令"
          style={{
            width: "100%",
            padding: 10,
            borderRadius: 8,
            background: "var(--field)",
            border: "1px solid var(--line)",
            color: "var(--ink)",
          }}
        />
        {err && (
          <p style={{ color: "var(--danger)", fontSize: 12, marginTop: 8, marginBottom: 0 }}>
            {err}
          </p>
        )}
        <button
          className="glow-btn"
          onClick={submit}
          disabled={checking}
          style={{
            width: "100%",
            marginTop: 12,
            padding: 11,
            border: "none",
            borderRadius: 8,
            color: "#fff",
            fontWeight: 700,
            cursor: checking ? "not-allowed" : "pointer",
            opacity: checking ? 0.7 : 1,
          }}
        >
          {checking ? "校验中…" : "进入"}
        </button>
      </div>
    </div>
  )
}
