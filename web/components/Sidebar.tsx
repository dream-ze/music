import Link from "next/link"

const items = [
  { href: "/", label: "✦ 创作" },
  { href: "/library", label: "▤ 作品库" },
  { href: "/favorites", label: "♡ 我的收藏" },
]

export default function Sidebar() {
  return (
    <aside
      style={{
        width: 170,
        padding: "18px 12px",
        borderRight: "1px solid rgba(255,255,255,.5)",
        background: "rgba(255,255,255,.42)",
        backdropFilter: "blur(16px) saturate(1.1)",
        WebkitBackdropFilter: "blur(16px) saturate(1.1)",
      }}
    >
      {items.map((it) => (
        <Link
          key={it.href}
          href={it.href}
          className="text-muted"
          style={{
            display: "block",
            padding: "10px 12px",
            borderRadius: 9,
            textDecoration: "none",
            marginBottom: 4,
          }}
        >
          {it.label}
        </Link>
      ))}
    </aside>
  )
}
