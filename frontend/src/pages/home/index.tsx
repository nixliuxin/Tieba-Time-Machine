import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { getForums, getStats, getSources, addSource, removeSource, encodeForumKey } from '@/lib/api'
import type { Forum, Stats, SourcesResponse } from '@/lib/api'

export default function Home() {
  const { data: forums, isLoading: forumsLoading } = useQuery({
    queryKey: ['forums'],
    queryFn: getForums,
  })
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
  })
  const { data: sourcesData } = useQuery({
    queryKey: ['sources'],
    queryFn: getSources,
  })

  const hasForums = forums && forums.length > 0

  if (forumsLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#F6F6F8]">
        <div className="text-[#9499A0]">加载中...</div>
      </div>
    )
  }

  if (!hasForums) {
    return <WelcomePage />
  }

  return <Dashboard forums={forums} stats={stats} sources={sourcesData} />
}

function WelcomePage() {
  const queryClient = useQueryClient()
  const [path, setPath] = useState('')
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: addSource,
    onSuccess: () => {
      setPath('')
      setError('')
      queryClient.invalidateQueries({ queryKey: ['forums'] })
      queryClient.invalidateQueries({ queryKey: ['sources'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const history = getPathHistory()

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#F6F6F8] px-[20px]">
      {/* Title */}
      <h1 className="mb-[40px] text-[42px] font-light text-[#333]">贴吧归档阅读器</h1>

      {/* Drop dialog */}
      <div className="w-full max-w-[700px] rounded-[25px] bg-white p-[40px] shadow-[0_4px_16px_rgba(0,0,0,0.08),0_2px_4px_rgba(0,0,0,0.04)]">
        <p className="mb-[20px] text-center text-[14px] text-[#9499A0]">
          输入贴吧归档目录路径，开始阅读
        </p>

        <form
          className="flex gap-[8px]"
          onSubmit={(e) => {
            e.preventDefault()
            if (path.trim()) {
              mutation.mutate(path.trim())
              savePathHistory(path.trim())
            }
          }}
        >
          <input
            type="text"
            value={path}
            onChange={(e) => { setPath(e.target.value); setError('') }}
            placeholder="粘贴归档路径，如 D:\archives\魔兽世界"
            className="flex-1 border border-[#dcdfe6] bg-[#f8f9fa] px-[16px] py-[10px] text-[14px] text-[#333] placeholder:text-[#c0c4cc] focus:border-[#409EFF] focus:outline-none"
          />
          <button
            type="submit"
            disabled={mutation.isPending || !path.trim()}
            className="shrink-0 bg-[#409EFF] px-[24px] py-[10px] text-[14px] font-medium text-white hover:bg-[#66b1ff] disabled:opacity-50"
          >
            {mutation.isPending ? '加载中...' : '打开'}
          </button>
        </form>

        {error && (
          <p className="mt-[12px] text-[13px] text-red-500">{error}</p>
        )}

        {history.length > 0 && (
          <div className="mt-[20px]">
            <p className="mb-[8px] text-[12px] text-[#9499A0]">最近打开</p>
            <div className="space-y-[4px]">
              {history.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => { setPath(p); mutation.mutate(p) }}
                  className="block w-full truncate px-[8px] py-[6px] text-left text-[13px] text-[#606266] hover:bg-[#f5f7fa] hover:text-[#409EFF]"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Dashboard({
  forums,
  stats,
  sources,
}: {
  forums: Forum[]
  stats?: Stats
  sources?: SourcesResponse
}) {
  const queryClient = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [newPath, setNewPath] = useState('')
  const [addError, setAddError] = useState('')

  const addMutation = useMutation({
    mutationFn: addSource,
    onSuccess: () => {
      setNewPath('')
      setAddError('')
      setShowAdd(false)
      queryClient.invalidateQueries({ queryKey: ['forums'] })
      queryClient.invalidateQueries({ queryKey: ['sources'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
    onError: (err: Error) => setAddError(err.message),
  })

  const removeMutation = useMutation({
    mutationFn: removeSource,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['forums'] })
      queryClient.invalidateQueries({ queryKey: ['sources'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })

  return (
    <div className="min-h-screen bg-[#F6F6F8]">
      {/* Header */}
      <DashboardHeader showAdd={showAdd} onToggleAdd={() => setShowAdd(!showAdd)} />

      <div className="mx-auto max-w-[960px] px-[20px] py-[24px]">
        {/* Stats row */}
        {stats && (
          <div className="mb-[20px] flex gap-[12px]">
            <StatCard label="贴吧" value={stats.forums} />
            <StatCard label="主题" value={stats.threads} />
            <StatCard label="帖子" value={stats.posts} />
            <StatCard label="媒体" value={stats.media_files} />
          </div>
        )}

        {/* Add source panel */}
        {showAdd && (
          <div className="mb-[20px] rounded-[8px] border border-[#e4e6eb] bg-white p-[20px]">
            <form
              className="flex gap-[8px]"
              onSubmit={(e) => {
                e.preventDefault()
                if (newPath.trim()) {
                  addMutation.mutate(newPath.trim())
                  savePathHistory(newPath.trim())
                }
              }}
            >
              <input
                type="text"
                value={newPath}
                onChange={(e) => { setNewPath(e.target.value); setAddError('') }}
                placeholder="归档目录路径..."
                className="flex-1 border border-[#dcdfe6] px-[12px] py-[8px] text-[13px] placeholder:text-[#c0c4cc] focus:border-[#409EFF] focus:outline-none"
              />
              <button
                type="submit"
                disabled={addMutation.isPending || !newPath.trim()}
                className="bg-[#409EFF] px-[16px] py-[8px] text-[13px] text-white hover:bg-[#66b1ff] disabled:opacity-50"
              >
                添加
              </button>
            </form>
            {addError && <p className="mt-[8px] text-[13px] text-red-500">{addError}</p>}
            {sources && (
              <div className="mt-[12px]">
                <p className="mb-[6px] text-[12px] text-[#9499A0]">已加载的数据源</p>
                {sources.sources.map((s) => (
                  <div key={s} className="flex items-center justify-between py-[4px] text-[13px]">
                    <span className="truncate text-[#606266]">{s}</span>
                    <button
                      type="button"
                      onClick={() => removeMutation.mutate(s)}
                      className="ml-[12px] shrink-0 text-[12px] text-red-400 hover:text-red-600"
                    >
                      移除
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Forum list */}
        <h2 className="mb-[12px] text-[14px] font-bold text-[#333]">已加载的贴吧</h2>
        <div className="space-y-[8px]">
          {forums.map((forum) => (
            <div
              key={forum.forum_name}
              className="rounded-[8px] border border-[#e4e6eb] bg-white p-[16px] transition-shadow hover:shadow-[0_2px_8px_rgba(0,0,0,0.06)]"
            >
              <div className="flex items-center gap-[12px]">
                <div className="flex h-[48px] w-[48px] shrink-0 items-center justify-center rounded-[6px] bg-gradient-to-br from-[#4096ff] to-[#69b4ff] text-[18px] font-bold text-white">
                  {forum.forum_name[0]}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-[6px]">
                    <Link
                      to="/forums/$forumKey"
                      params={{ forumKey: encodeForumKey(forum.forum_key) }}
                      className="text-[15px] font-bold text-[#18191C] hover:text-[#4096ff]"
                    >
                      {forum.forum_name}吧
                    </Link>
                    {forum.collection && (
                      <span className="inline-flex h-[18px] items-center rounded-[3px] bg-[#f0f5ff] px-[5px] text-[10px] font-medium text-[#4096ff]">
                        📁 {forum.collection}
                      </span>
                    )}
                    {!forum.collection && forum.forum_key.toLowerCase() !== forum.forum_name.toLowerCase() && (
                      <span className="inline-flex h-[18px] items-center rounded-[3px] bg-[#fff7e6] px-[5px] text-[10px] font-medium text-[#d48806]">
                        归档: {forum.forum_key}
                      </span>
                    )}
                    <a
                      href={`https://tieba.baidu.com/f?kw=${encodeURIComponent(forum.forum_name)}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] text-[#c0c4cc] hover:text-[#4096ff]"
                      title="在百度贴吧查看"
                      onClick={(e) => e.stopPropagation()}
                    >
                      ↗
                    </a>
                  </div>
                  {forum.slogan && (
                    <p className="mt-[2px] truncate text-[12px] text-[#9499A0]">{forum.slogan}</p>
                  )}
                  <div className="mt-[4px] flex items-center gap-[12px] text-[11px] text-[#9499A0]">
                    {forum.member_num > 0 && <span>关注 {forum.member_num.toLocaleString()}</span>}
                    <span>归档 {forum.archived_threads} 帖</span>
                    {forum.media_files > 0 && <span>媒体 {forum.media_files}</span>}
                  </div>
                </div>
                <Link
                  to="/forums/$forumKey"
                  params={{ forumKey: encodeForumKey(forum.forum_key) }}
                  className="shrink-0 rounded-[4px] border border-[#e8e8e8] px-[12px] py-[6px] text-[12px] text-[#666] hover:border-[#4096ff] hover:text-[#4096ff]"
                >
                  查看
                </Link>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex-1 rounded-[8px] border border-[#e4e6eb] bg-white px-[12px] py-[14px] text-center">
      <div className="text-[22px] font-bold leading-[1] text-[#222]">{value.toLocaleString()}</div>
      <div className="mt-[6px] text-[11px] font-medium uppercase tracking-wider text-[#9499A0]">{label}</div>
    </div>
  )
}

function DashboardHeader({ showAdd, onToggleAdd }: { showAdd: boolean; onToggleAdd: () => void }) {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')

  return (
    <header className="sticky top-0 z-20 flex items-center gap-[16px] border-b border-[#e4e6eb] bg-white px-[24px] py-[10px]">
      <h1 className="shrink-0 text-[16px] font-bold text-[#333]">贴吧归档阅读器</h1>
      <form
        className="flex-1"
        onSubmit={(e) => {
          e.preventDefault()
          if (searchQuery.trim()) {
            navigate({ to: '/search', search: { q: searchQuery.trim() } })
          }
        }}
      >
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="搜索帖子..."
          className="w-full max-w-[400px] rounded-[4px] border border-[#dcdfe6] bg-[#f8f9fa] px-[12px] py-[6px] text-[13px] placeholder:text-[#c0c4cc] focus:border-[#4096ff] focus:outline-none"
        />
      </form>
      <button
        type="button"
        onClick={onToggleAdd}
        className="shrink-0 rounded-[4px] border border-[#4096ff] px-[12px] py-[5px] text-[13px] text-[#4096ff] hover:bg-[#4096ff] hover:text-white"
      >
        {showAdd ? '收起' : '+ 添加数据源'}
      </button>
    </header>
  )
}

const HISTORY_KEY = 'tieba-reader-path-history'

function getPathHistory(): string[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function savePathHistory(path: string) {
  const history = getPathHistory().filter((p) => p !== path)
  history.unshift(path)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 10)))
}
