"use client"
import { useState, useEffect } from "react"
import { getPasscode, setPasscode } from "@/lib/passcode"

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"

async function verify(passcode: string): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/api/songs?limit=1`, {
      headers: { "X-Passcode": passcode },
    })
    return res.ok
  } catch {
    return false
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
    verify(saved).then((good) => {
      setOk(good)
      if (!good) setErr("已保存的口令无效，请重新输入")
      setReady(true)
    })
  }, [])

  async function submit() {
    if (!val) return
    setChecking(true)
    setErr("")
    const good = await verify(val)
    setChecking(false)
    if (good) {
      setPasscode(val)
      setOk(true)
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
        <h2 style={{ marginTop: 0 }}>🎵 ze music</h2>
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
            background: "var(--bg)",
            border: "1px solid var(--line)",
            color: "var(--ink)",
          }}
        />
        {err && (
          <p style={{ color: "#ff7a8a", fontSize: 12, marginTop: 8, marginBottom: 0 }}>
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
