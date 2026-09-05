import type { Config } from "tailwindcss"

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        panel: "var(--panel)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        brand: "var(--brand)",
        brand2: "var(--brand2)",
        line: "var(--line)",
      },
    },
  },
  plugins: [],
} satisfies Config
