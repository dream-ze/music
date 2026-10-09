export const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE ??
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "")
).replace(/\/+$/, "")

export function mediaUrl(url: string): string {
  return url.startsWith("/api/media/") ? `${API_BASE}${url}` : url
}
