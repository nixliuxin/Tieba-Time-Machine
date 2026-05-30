import { useQuery } from '@tanstack/react-query'
import { Link, useParams, useSearch, useNavigate } from '@tanstack/react-router'
import { useState, useMemo } from 'react'
import { getThread, getForums, encodeForumKey } from '@/lib/api'
import type { Post } from '@/lib/api'
import { PostCard } from '@/components/tieba/post-card'
import { ThreadSidebar } from '@/components/tieba/sidebar'
import { TiebaPostLink } from '@/components/tieba/external-link'

const PAGE_SIZE = 30

type SortMode = 'asc' | 'desc' | 'agree' | 'reply'
type FilterMode = 'all' | 'author' | 'author_reply'

export default function ThreadPage() {
  const { tid } = useParams({ strict: false }) as { tid: string }
  const searchParams = useSearch({ strict: false }) as { page?: string }
  const navigate = useNavigate()
  const tidNum = Number(tid)

  const [sort, setSort] = useState<SortMode>('asc')
  const [filter, setFilter] = useState<FilterMode>('all')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true)
  const page = Number(searchParams.page) || 1

  const { data, isLoading, error } = useQuery({
    queryKey: ['thread', tidNum],
    queryFn: () => getThread(tidNum),
    enabled: !!tidNum,
  })

  const { data: forums } = useQuery({
    queryKey: ['forums'],
    queryFn: getForums,
  })

  const forum = useMemo(() => {
    if (!data || !forums) return undefined
    return forums.find((f) => f.forum_name === data.thread.forum_name)
  }, [data, forums]) // eslint-disable-line react-hooks/exhaustive-deps

  const { sortedPosts, totalPages } = useMemo(() => {
    if (!data) return { sortedPosts: [], totalPages: 0 }

    let posts = [...data.posts]

    if (filter === 'author') {
      posts = posts.filter((p) => p.is_thread_author)
    } else if (filter === 'author_reply') {
      const authorPosts = new Set(posts.filter((p) => p.is_thread_author).map((p) => p.id))
      posts = posts.filter((p) => p.is_thread_author || data.sub_posts.some((sp) => sp.parent_id && authorPosts.has(sp.parent_id)))
    }

    switch (sort) {
      case 'desc':
        posts.sort((a, b) => b.floor - a.floor)
        break
      case 'agree':
        posts.sort((a, b) => b.agree - a.agree)
        break
      case 'reply':
        posts.sort((a, b) => b.reply_num - a.reply_num)
        break
      default:
        posts.sort((a, b) => a.floor - b.floor)
    }

    const total = Math.ceil(posts.length / PAGE_SIZE)
    const start = (page - 1) * PAGE_SIZE
    return { sortedPosts: posts.slice(start, start + PAGE_SIZE), totalPages: total }
  }, [data, sort, filter, page])

  const subPostsByParent = useMemo(() => {
    if (!data) return {}
    const map: Record<number, Post[]> = {}
    for (const sp of data.sub_posts) {
      if (!map[sp.parent_id]) map[sp.parent_id] = []
      map[sp.parent_id]!.push(sp)
    }
    return map
  }, [data])

  if (isLoading) {
    return <div className="flex min-h-[60vh] items-center justify-center text-[#9499A0]">加载中...</div>
  }
  if (error) {
    return <div className="flex min-h-[60vh] items-center justify-center text-red-500">加载失败: {String(error)}</div>
  }
  if (!data) return null

  const { thread, users, media_files, forum_dir } = data

  return (
    <div className="flex min-h-screen bg-white">
      {/* Sidebar */}
      <ThreadSidebar
        forum={forum}
        threadMeta={{
          create_time: thread.create_time,
          reply_num: thread.reply_num,
          view_num: thread.view_num,
          agree: thread.agree,
        }}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main content */}
      <main className="min-w-0 flex-1">
        {/* Thread header - sticky, mimics original Tieba */}
        <div className="sticky top-0 z-10 border-b border-[#e4e6eb] bg-white px-[20px] py-[10px] shadow-[0_1px_2px_rgba(0,0,0,0.05)]">
          {/* Top row: breadcrumb + external link */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-[6px] text-[12px]">
              <Link to="/" className="text-[#4096ff] hover:underline">首页</Link>
              <span className="text-[#ddd]">›</span>
              <Link
                to="/forums/$forumKey"
                params={{ forumKey: encodeForumKey(forum_dir) }}
                className="text-[#4096ff] hover:underline"
              >
                {thread.forum_name}吧
              </Link>
              <span className="text-[#ddd]">›</span>
              <span className="text-[#555]">正文</span>
            </div>
            <TiebaPostLink tid={tidNum} />
          </div>

          {/* Thread title - large like original */}
          <h1 className="mt-[8px] text-[20px] font-bold leading-[30px] text-[#111]">
            {thread.title}
          </h1>

          {/* Meta + controls row */}
          <div className="mt-[8px] flex items-center">
            <div className="flex items-center gap-[14px] text-[13px] text-[#555]">
              <span>{thread.reply_num} 回复贴，共{totalPages || 1}页</span>
            </div>
            <div className="ml-auto flex items-center gap-[6px]">
              <button
                type="button"
                onClick={() => setFilter(filter === 'author' ? 'all' : 'author')}
                className={`rounded-[3px] border px-[10px] py-[3px] text-[12px] font-medium ${
                  filter === 'author'
                    ? 'border-[#4096ff] bg-[#4096ff] text-white'
                    : 'border-[#ddd] text-[#555] hover:border-[#4096ff] hover:text-[#4096ff]'
                }`}
              >
                只看楼主
              </button>
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as SortMode)}
                className="h-[28px] cursor-pointer rounded-[3px] border border-[#ddd] bg-white px-[8px] text-[12px] text-[#555] outline-none hover:border-[#4096ff]"
              >
                <option value="asc">正序</option>
                <option value="desc">倒序</option>
                <option value="agree">最多赞</option>
              </select>
            </div>
          </div>
        </div>

        {/* Posts list */}
        <div className="mx-auto max-w-[900px]">
          {sortedPosts.map((post) => (
            <PostCard
              key={post.id}
              post={post}
              users={users}
              subPosts={subPostsByParent[post.id]}
              forumName={forum_dir || thread.forum_name}
              mediaFiles={media_files}
              tid={tidNum}
            />
          ))}
        </div>

        {sortedPosts.length === 0 && (
          <div className="py-[60px] text-center text-[#9499A0]">暂无内容</div>
        )}

        {/* Pagination footer */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-[4px] py-[10px] text-[13px]">
            {page > 1 && (
              <button
                type="button"
                onClick={() => navigate({ search: { page: page - 1 } as any })}
                className="h-[28px] border border-[#dcdfe6] bg-white px-[10px] text-[#606266] hover:text-[#409EFF]"
              >
                上一页
              </button>
            )}
            {Array.from({ length: Math.min(totalPages, 10) }, (_, i) => {
              const p = i + 1
              return (
                <button
                  key={p}
                  type="button"
                  onClick={() => navigate({ search: { page: p } as any })}
                  className={`h-[28px] min-w-[28px] border px-[6px] ${
                    p === page
                      ? 'border-[#409EFF] bg-[#409EFF] text-white'
                      : 'border-[#dcdfe6] bg-white text-[#606266] hover:text-[#409EFF]'
                  }`}
                >
                  {p}
                </button>
              )
            })}
            {page < totalPages && (
              <button
                type="button"
                onClick={() => navigate({ search: { page: page + 1 } as any })}
                className="h-[28px] border border-[#dcdfe6] bg-white px-[10px] text-[#606266] hover:text-[#409EFF]"
              >
                下一页
              </button>
            )}
            <span className="ml-[10px] text-[#9499A0]">共 {totalPages} 页</span>
          </div>
        )}
      </main>

      {/* Back to top */}
      <button
        type="button"
        onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
        className="fixed bottom-[100px] right-[100px] z-50 flex h-[40px] w-[40px] items-center justify-center rounded border border-[#dcdfe6] bg-white text-[18px] text-[#606266] shadow-sm hover:text-[#409EFF]"
        title="回到顶部"
      >
        ↑
      </button>
    </div>
  )
}
