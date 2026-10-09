import type { Song, Job, ActiveJob, GenerateInput, Inspiration, Category, Styles } from "./types"
import { getPasscode } from "./passcode"

import { API_BASE as BASE } from "./api-base"

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
  // job_ids:count=2 时有两个任务;job_id 是第一个(兼容旧写法)
  return req<{ job_id: string; job_ids?: string[] }>("/api/generate", {
    method: "POST",
    body: JSON.stringify(input),
  })
}

export function getJob(jobId: string) {
  return req<Job>(`/api/jobs/${jobId}`)
}

export async function listActiveJobs(): Promise<ActiveJob[]> {
  const r = await req<{ jobs: ActiveJob[] }>("/api/jobs/active")
  return r.jobs
}

export async function listSongs(
  params: { q?: string; favorite?: boolean; mine?: string; category?: string } = {}
): Promise<Song[]> {
  const qs = new URLSearchParams()
  if (params.q) qs.set("q", params.q)
  if (params.favorite) qs.set("favorite", "true")
  if (params.mine) qs.set("mine", params.mine)
  if (params.category) qs.set("category", params.category)
  const r = await req<{ songs: Song[] }>(`/api/songs?${qs.toString()}`)
  return r.songs
}

export async function toggleFavorite(id: string): Promise<boolean> {
  const r = await req<{ favorite: boolean }>(`/api/songs/${id}/favorite`, {
    method: "POST",
  })
  return r.favorite
}

export async function deleteSong(id: string): Promise<void> {
  await req<{ deleted: boolean }>(`/api/songs/${id}`, { method: "DELETE" })
}

export async function renameSong(id: string, title: string): Promise<string> {
  const r = await req<{ title: string }>(`/api/songs/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  })
  return r.title
}

export async function listCategories(): Promise<Category[]> {
  const r = await req<{ categories: Category[] }>("/api/categories")
  return r.categories
}

export function createCategory(name: string): Promise<Category> {
  return req<Category>("/api/categories", {
    method: "POST",
    body: JSON.stringify({ name }),
  })
}

export async function deleteCategory(id: string): Promise<void> {
  await req<{ deleted: boolean }>(`/api/categories/${id}`, { method: "DELETE" })
}

export async function addSongToCategory(songId: string, categoryId: string): Promise<string[]> {
  const r = await req<{ category_ids: string[] }>(
    `/api/songs/${songId}/categories/${categoryId}`,
    { method: "PUT" }
  )
  return r.category_ids
}

export async function removeSongFromCategory(songId: string, categoryId: string): Promise<string[]> {
  const r = await req<{ category_ids: string[] }>(
    `/api/songs/${songId}/categories/${categoryId}`,
    { method: "DELETE" }
  )
  return r.category_ids
}

export async function getInspirations() {
  const r = await req<{ inspirations: Inspiration[] }>("/api/inspirations")
  return r.inspirations
}

export function getStyles() {
  return req<Styles>("/api/styles")
}
