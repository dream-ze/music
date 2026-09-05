"use client"
import { useState, useEffect } from "react"
import { getPasscode, setPasscode } from "@/lib/passcode"

export default function PasscodeGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false)
  const [ok, setOk] = useState(false)
  const [val, setVal] = useState("")

  useEffect(() => {
    setOk(getPasscode().length > 0)
    setReady(true)
  }, [])
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
        <button
          className="glow-btn"
          onClick={() => {
            setPasscode(val)
            setOk(val.length > 0)
          }}
          style={{
            width: "100%",
            marginTop: 12,
            padding: 11,
            border: "none",
            borderRadius: 8,
            color: "#fff",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          进入
        </button>
      </div>
    </div>
  )
}
