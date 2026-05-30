const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8900'

async function fetchApi<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(`${API_BASE}${path}`)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value))
      }
    }
  }
  const res = await fetch(url.toString())
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
  return res.json()
}

export interface Forum {
  forum_id: number
  forum_key: string
  forum_name: string
  collection?: string
  member_num: number
  post_num: number
  thread_num: number
  slogan: string
  archived_threads: number
  media_files: number
}

/**
 * Encode forum_key for use in URLs.
 * Replaces '/' with '~' so "User_example/分类" becomes "User_example~分类"
 */
export function encodeForumKey(key: string): string {
  return encodeURIComponent(key.replace(/\//g, '~'))
}

export function decodeForumKey(encoded: string): string {
  return decodeURIComponent(encoded).replace(/~/g, '/')
}

export interface ThreadItem {
  tid: number
  title: string
  forum_name: string
  view_num: number
  reply_num: number
  agree: number
  create_time: number
  last_time: number
  status: number
  author_name?: string
  snippet?: string
}

export interface ThreadList {
  total: number
  page: number
  page_size: number
  items: ThreadItem[]
}

export interface Post {
  id: number
  floor: number
  contents: string
  user_id: number
  agree: number
  disagree: number
  create_time: number
  is_thread_author: boolean
  sign: string
  reply_num: number
  parent_id: number
  reply_to_id: number
}

export interface UserInfo {
  portrait: string
  nickname: string
  username: string
  avatar: string
  level: number
  gender: number
  ip: string
  is_vip: boolean
}

export interface ThreadDetail {
  thread: ThreadItem & {
    vote_info: string
    folder_name: string
  }
  forum_dir: string
  posts: Post[]
  sub_posts: Post[]
  users: Record<string, UserInfo>
  media_files: string[]
}

export interface Stats {
  forums: number
  threads: number
  posts: number
  users: number
  earliest_time: number
  latest_time: number
  media_files: number
}

export function getForums() {
  return fetchApi<Forum[]>('/api/forums')
}

export async function getForumDetail(forumName: string): Promise<Forum | null> {
  const forums = await getForums()
  return forums.find(f => f.forum_name === forumName) || null
}

export function getStats() {
  return fetchApi<Stats>('/api/stats')
}

export function getThreads(params: {
  forum?: string
  page?: number
  page_size?: number
  q?: string
  sort?: string
  order?: string
}) {
  return fetchApi<ThreadList>('/api/threads', params as Record<string, string | number>)
}

export function getThread(tid: number) {
  return fetchApi<ThreadDetail>(`/api/thread/${tid}`)
}

export function getSearchSuggest(q: string) {
  return fetchApi<Array<{ tid: number; title: string; forum_name: string }>>('/api/search/suggest', { q })
}

export function getMediaUrl(forum: string, path: string) {
  return `${API_BASE}/api/media/${encodeURIComponent(forum)}/${path}`
}

export interface SourcesResponse {
  sources: string[]
  forums_loaded: number
}

export function getSources() {
  return fetchApi<SourcesResponse>('/api/sources')
}

export async function addSource(path: string): Promise<SourcesResponse> {
  const res = await fetch(`${API_BASE}/api/sources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `Error ${res.status}`)
  }
  return res.json()
}

export async function removeSource(path: string): Promise<SourcesResponse> {
  const res = await fetch(`${API_BASE}/api/sources`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `Error ${res.status}`)
  }
  return res.json()
}
