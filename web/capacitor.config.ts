import type { CapacitorConfig } from "@capacitor/cli"

const config: CapacitorConfig = {
  appId: "com.zemusic.app",
  appName: "ze music",
  webDir: "out-apk",
  server: { androidScheme: "https" },
}
export default config
