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
        <div className="snow-bg" aria-hidden />
        <div className="app-shell">
          <PasscodeGate>
            <PlayerProvider>
              <Nav />
              <div className="layout-body">
                <Sidebar />
                <main className="layout-main">
                  {children}
                </main>
              </div>
              <Player />
            </PlayerProvider>
          </PasscodeGate>
        </div>
      </body>
    </html>
  )
}
