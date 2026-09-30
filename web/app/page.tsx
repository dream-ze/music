import GenerateForm from "@/components/GenerateForm"

export default function Home() {
  return (
    <div>
      <h1 style={{ fontSize: 26, fontWeight: 800, margin: "0 0 4px" }}>
        灵感壁炉
      </h1>
      <p className="text-muted" style={{ margin: "0 0 18px" }}>
        Where Beats Crackle
      </p>
      <GenerateForm />
    </div>
  )
}
