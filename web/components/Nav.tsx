import Link from "next/link"

const items = [
  { href: "/", label: "创作" },
  { href: "/library", label: "作品库" },
  { href: "/favorites", label: "我的收藏" },
]

export default function Nav() {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        gap: 26,
        padding: "14px 22px",
        borderBottom: "1px solid var(--line)",
        background: "#0e0b1c",
      }}
    >
      <div style={{ fontWeight: 800, fontSize: 16 }}>
        🎵{" "}
        <span
          style={{
            background: "linear-gradient(90deg,#b06bff,#5c7cff)",
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            color: "transparent",
          }}
        >
          ze music
        </span>
      </div>
      <nav style={{ display: "flex", gap: 20 }}>
        {items.map((it) => (
          <Link
            key={it.href}
            href={it.href}
            className="text-muted"
            style={{ textDecoration: "none" }}
          >
            {it.label}
          </Link>
        ))}
      </nav>
      <div
        style={{
          marginLeft: "auto",
          width: 30,
          height: 30,
          borderRadius: "50%",
          background: "linear-gradient(135deg,#b06bff,#5c7cff)",
        }}
      />
    </header>
  )
}
