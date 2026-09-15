export interface Song {
  id: string
  title: string
  lyrics: string
  feeling: string
  spec_json: string
  structured_lyrics: string
  seed: number | null
  mp3_url: string
  duration_sec: number
  instrumental: number
  created_by: string
  favorite: number
  created_at: string
  /** JSON 字符串:[{stage, ok}]。老歌为空 —— 那时还没有这个字段。 */
  llm_status?: string | null
}

export interface Job {
  status: "queued" | "running" | "done" | "error"
  position: number | null
  song: Song | null
  error: string | null
}

export interface GenerateInput {
  lyrics: string
  feeling: string
  length: "full" | "short"
  seed: number | null
  instrumental: boolean
  overrides: {
    genre?: string[]
    mood?: string[]
    vocal_gender?: string
    language?: string
    preset?: string
  }
}

export interface Inspiration {
  title: string
  feeling: string
  lyrics: string
  /** 风格预设 id;空表示不预选 */
  preset: string
}
