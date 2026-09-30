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
  /** 这首歌当前所在的分类 id 列表;跟网易云歌单一样,能同时属于好几个。 */
  category_ids?: string[]
}

/** listSongs({category}) 传这个值 = 只看没分类的歌(后端 __none__ 语义) */
export const UNCATEGORIZED = "__none__"

/** 拖歌曲卡片到侧栏分类项时,dataTransfer 用这个 mime 类型传歌曲 id */
export const SONG_DRAG_MIME = "application/x-zemusic-song-id"

/** 自定义分类;一首歌能同时属于好几个分类,拖/勾选加进去,不会互相排斥 */
export interface Category {
  id: string
  name: string
  created_by: string
  created_at: string
  song_count: number
}

export interface Job {
  status: "queued" | "running" | "done" | "error"
  position: number | null
  song: Song | null
  error: string | null
}

/** 排队中/生成中的任务,作品库用来显示"生成中"卡片 */
export interface ActiveJob {
  job_id: string
  status: "queued" | "running"
  title: string
  feeling: string
  created_by: string
  created_at: string
}

export interface GenerateInput {
  lyrics: string
  /** 自定义歌名;空则后端自动命名 */
  title?: string
  feeling: string
  /** auto = 按歌词自动估算(前端唯一使用的挡位);full/short 只留给内部/测试用 */
  length: "auto" | "full" | "short"
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
