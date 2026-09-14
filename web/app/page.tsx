import GenerateForm from "@/components/GenerateForm"

export default function Home() {
  return (
    <div>
      <h1 style={{ fontSize: 26, fontWeight: 800, margin: "0 0 4px" }}>
        用{" "}
        <span
          style={{
            background: "linear-gradient(90deg,#2f6bd8,#62aee6)",
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            color: "transparent",
          }}
        >
          AI
        </span>{" "}
        创作你的音乐
      </h1>
      <p className="text-muted" style={{ margin: "0 0 18px" }}>
        输入歌词,再用一句话说说你想要的感觉,剩下的交给 AI
      </p>
      <GenerateForm />
    </div>
  )
}
