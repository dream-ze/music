import "./globals.css"
import Nav from "@/components/Nav"
import Sidebar from "@/components/Sidebar"
import Player from "@/components/Player"
import PasscodeGate from "@/components/PasscodeGate"
import { PlayerProvider } from "@/lib/player"

export const metadata = { title: "ze music", description: "把歌词变成一首歌" }

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body>
        <PasscodeGate>
          <PlayerProvider>
            <Nav />
            <div style={{ display: "flex", minHeight: "calc(100vh - 59px)" }}>
              <Sidebar />
              <main style={{ flex: 1, padding: "22px 24px", paddingBottom: 90 }}>
                {children}
              </main>
            </div>
            <Player />
          </PlayerProvider>
        </PasscodeGate>
      </body>
    </html>
  )
}
