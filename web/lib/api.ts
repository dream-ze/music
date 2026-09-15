import type { Song, Job, GenerateInput, Inspiration } from "./types"
import { getPasscode } from "./passcode"

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Passcode": getPasscode(),
      ...(init.headers || {}),
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `请求失败 ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function generate(input: GenerateInput) {
  return req<{ job_id: string }>("/api/generate", {
    method: "POST",
    body: JSON.stringify(input),
  })
}

export function getJob(jobId: string) {
  return req<Job>(`/api/jobs/${jobId}`)
}

export async function listSongs(
  params: { q?: string; favorite?: boolean; mine?: string } = {}
): Promise<Song[]> {
  const qs = new URLSearchParams()
  if (params.q) qs.set("q", params.q)
  if (params.favorite) qs.set("favorite", "true")
  if (params.mine) qs.set("mine", params.mine)
  const r = await req<{ songs: Song[] }>(`/api/songs?${qs.toString()}`)
  return r.songs
}

export async function toggleFavorite(id: string): Promise<boolean> {
  const r = await req<{ favorite: boolean }>(`/api/songs/${id}/favorite`, {
    method: "POST",
  })
  return r.favorite
}

export async function getInspirations() {
  const r = await req<{ inspirations: Inspiration[] }>("/api/inspirations")
  return r.inspirations
}
