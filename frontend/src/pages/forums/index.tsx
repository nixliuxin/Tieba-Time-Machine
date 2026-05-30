import { useQuery } from '@tanstack/react-query'
import { Link, useParams, useSearch } from '@tanstack/react-router'
import { getThreads, getForums, decodeForumKey, encodeForumKey } from '@/lib/api'
import { TiebaForumLink, TiebaPostLink } from '@/components/tieba/external-link'

export default function ForumPage() {
  const { forumKey: encodedKey } = useParams({ strict: false }) as { forumKey: string }
  const searchParams = useSearch({ strict: false }) as { page?: string; sort?: string; order?: string }

  const forumKey = decodeForumKey(encodedKey)
  const page = Number(searchParams.page) || 1
  const sort = searchParams.sort || 'create_time'
  const order = searchParams.order || 'desc'

  const { data, isLoading } = useQuery({
    queryKey: ['threads', forumKey, page, sort, order],
    queryFn: () => getThreads({ forum: forumKey, page, sort, order }),
  })

  const { data: forums } = useQuery({
    queryKey: ['forums'],
    queryFn: getForums,
  })

  const forum = forums?.find((f) => f.forum_key === forumKey)
  const forumName = forum?.forum_name || forumKey.split('/').pop() || forumKey
  const collection = forum?.collection
  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0

  return (
    <div className="min-h-screen bg-[#f4f5f7]">
      {/* Sticky top header */}
      <header className="sticky top-0 z-20 border-b border-[#ddd] bg-white">
        <div className="mx-auto flex max-w-[1140px] items-center gap-[14px] px-[24px] py-[10px]">
          <Link to="/" className="text-[13px] font-medium text-[#4096ff] hover:underline">
            ← 首页
          </Link>
          <div className="h-[16px] w-[1px] bg-[#ddd]" />
          <div className="flex items-center gap-[8px]">
            <div className="flex h-[32px] w-[32px] items-center justify-center rounded-[4px] bg-[#4096ff] text-[13px] font-bold text-white">
              {forumName[0]}
            </div>
            <h1 className="text-[15px] font-bold text-[#222]">{forumName}吧</h1>
          </div>
          <TiebaForumLink forumName={forumName} />
          {forum && (
            <div className="ml-auto flex items-center gap-[14px] text-[12px] text-[#666]">
              {forum.member_num > 0 && <span>关注 <b className="text-[#333]">{formatNum(forum.member_num)}</b></span>}
              {forum.thread_num > 0 && <span>主题 <b className="text-[#333]">{formatNum(forum.thread_num)}</b></span>}
              <span>已归档 <b className="text-[#333]">{forum.archived_threads}</b></span>
            </div>
          )}
        </div>
      </header>

      {/* Two-column layout */}
      <div className="mx-auto flex max-w-[1140px] gap-[16px] px-[24px] py-[16px]">
        {/* Left: main content */}
        <div className="min-w-0 flex-1">
          {/* Forum info card - always show */}
          <div className="mb-[12px] rounded-[6px] bg-white p-[18px] shadow-[0_1px_4px_rgba(0,0,0,0.06)]">
            <div className="flex items-start gap-[14px]">
              <div className="flex h-[56px] w-[56px] shrink-0 items-center justify-center rounded-[6px] bg-gradient-to-br from-[#4096ff] to-[#69b4ff] text-[22px] font-bold text-white">
                {forumName[0]}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-[8px]">
                  <h2 className="text-[18px] font-bold text-[#111]">{forumName}吧</h2>
                  {collection && (
                    <span className="inline-flex h-[20px] items-center rounded-[3px] bg-[#f0f5ff] px-[6px] text-[11px] font-medium text-[#4096ff]">
                      📁 {collection}
                    </span>
                  )}
                  {!collection && forumKey.toLowerCase() !== forumName.toLowerCase() && (
                    <span className="inline-flex h-[20px] items-center rounded-[3px] bg-[#fff7e6] px-[6px] text-[11px] font-medium text-[#d48806]">
                      归档: {forumKey}
                    </span>
                  )}
                </div>
                {forum?.slogan && (
                  <p className="mt-[4px] text-[13px] leading-[20px] text-[#555]">{forum.slogan}</p>
                )}
                <div className="mt-[10px] flex flex-wrap gap-[20px] text-[13px]">
                  {forum && forum.member_num > 0 && (
                    <div>
                      <span className="text-[18px] font-bold text-[#222]">{forum.member_num.toLocaleString()}</span>
                      <span className="ml-[4px] text-[#777]">关注</span>
                    </div>
                  )}
                  {forum && forum.thread_num > 0 && (
                    <div>
                      <span className="text-[18px] font-bold text-[#222]">{forum.thread_num.toLocaleString()}</span>
                      <span className="ml-[4px] text-[#777]">主题</span>
                    </div>
                  )}
                  {forum && forum.post_num > 0 && (
                    <div>
                      <span className="text-[18px] font-bold text-[#222]">{forum.post_num.toLocaleString()}</span>
                      <span className="ml-[4px] text-[#777]">帖子</span>
                    </div>
                  )}
                  <div>
                    <span className="text-[18px] font-bold text-[#222]">{forum?.archived_threads ?? 0}</span>
                    <span className="ml-[4px] text-[#777]">已归档</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Thread list card */}
          <div className="overflow-hidden rounded-[6px] bg-white shadow-[0_1px_4px_rgba(0,0,0,0.06)]">
            {/* Sort tabs */}
            <div className="flex items-center border-b border-[#eee] px-[18px]">
              {(['create_time', 'reply_num', 'view_num', 'agree'] as const).map((s) => (
                <Link
                  key={s}
to="/forums/$forumKey"
                params={{ forumKey: encodedKey }}
                  search={{ sort: s, order: s === sort && order === 'desc' ? 'asc' : 'desc', page: 1 }}
                  className={`relative py-[12px] pr-[20px] text-[13px] font-medium transition-colors ${
                    s === sort
                      ? 'text-[#4096ff] after:absolute after:bottom-0 after:left-0 after:right-[20px] after:h-[2px] after:bg-[#4096ff] after:content-[""]'
                      : 'text-[#555] hover:text-[#4096ff]'
                  }`}
                >
                  {{ create_time: '最新发帖', reply_num: '最多回复', view_num: '最多浏览', agree: '最多点赞' }[s]}
                  {s === sort && <span className="ml-[2px]">{order === 'desc' ? '↓' : '↑'}</span>}
                </Link>
              ))}
              <div className="ml-auto text-[12px] text-[#888]">
                共 {data?.total ?? 0} 个主题
              </div>
            </div>

            {/* Thread list */}
            {isLoading && <div className="py-[60px] text-center text-[14px] text-[#888]">加载中...</div>}

            {data && data.items.length > 0 && (
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-[#f0f0f0] bg-[#f9fafb] text-[12px] text-[#888]">
                    <th className="w-[55px] py-[8px] text-center font-normal">回复</th>
                    <th className="py-[8px] pl-[14px] font-normal">标题</th>
                    <th className="w-[90px] py-[8px] text-center font-normal">作者</th>
                    <th className="w-[70px] py-[8px] text-center font-normal">浏览</th>
                    <th className="w-[100px] py-[8px] pr-[18px] text-right font-normal">时间</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((thread) => (
                    <tr key={thread.tid} className="border-b border-[#f5f5f5] transition-colors hover:bg-[#f8faff]">
                      <td className="py-[11px] text-center">
                        <span className={`text-[13px] font-bold ${thread.reply_num > 50 ? 'text-[#e25042]' : thread.reply_num > 10 ? 'text-[#f60]' : 'text-[#555]'}`}>
                          {thread.reply_num}
                        </span>
                      </td>
                      <td className="py-[11px] pl-[14px]">
                        <Link
                          to="/threads/$tid"
                          params={{ tid: String(thread.tid) }}
                          className="block truncate text-[14px] font-medium text-[#222] hover:text-[#4096ff]"
                        >
                          {thread.title || `[tid: ${thread.tid}]`}
                        </Link>
                      </td>
                      <td className="py-[11px] text-center text-[12px] text-[#777]">
                        {thread.author_name || '-'}
                      </td>
                      <td className="py-[11px] text-center text-[12px] text-[#777]">
                        {thread.view_num.toLocaleString()}
                      </td>
                      <td className="py-[11px] pr-[18px] text-right text-[12px] text-[#777]">
                        {formatDate(thread.create_time)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {data && data.items.length === 0 && (
              <div className="py-[60px] text-center text-[14px] text-[#888]">暂无帖子</div>
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-[16px] flex items-center justify-center gap-[4px] text-[13px]">
              {page > 1 && (
                <Link
to="/forums/$forumKey"
                params={{ forumKey: encodedKey }}
                  search={{ page: page - 1, sort, order }}
                  className="inline-flex h-[32px] items-center rounded-[4px] border border-[#ddd] bg-white px-[12px] font-medium text-[#555] hover:border-[#4096ff] hover:text-[#4096ff]"
                >
                  上一页
                </Link>
              )}
              {generatePageNumbers(page, totalPages).map((p, i) =>
                p === '...' ? (
                  <span key={`ellipsis-${i}`} className="px-[6px] text-[#999]">…</span>
                ) : (
                  <Link
                    key={p}
to="/forums/$forumKey"
                params={{ forumKey: encodedKey }}
                    search={{ page: p as number, sort, order }}
                    className={`inline-flex h-[32px] min-w-[32px] items-center justify-center rounded-[4px] border px-[8px] font-medium ${
                      p === page
                        ? 'border-[#4096ff] bg-[#4096ff] text-white'
                        : 'border-[#ddd] bg-white text-[#555] hover:border-[#4096ff] hover:text-[#4096ff]'
                    }`}
                  >
                    {p}
                  </Link>
                ),
              )}
              {page < totalPages && (
                <Link
to="/forums/$forumKey"
                params={{ forumKey: encodedKey }}
                  search={{ page: page + 1, sort, order }}
                  className="inline-flex h-[32px] items-center rounded-[4px] border border-[#ddd] bg-white px-[12px] font-medium text-[#555] hover:border-[#4096ff] hover:text-[#4096ff]"
                >
                  下一页
                </Link>
              )}
              <span className="ml-[12px] text-[12px] text-[#888]">
                第 {page}/{totalPages} 页
              </span>
            </div>
          )}
        </div>

        {/* Right sidebar - sticky */}
        <div className="hidden w-[280px] shrink-0 lg:block">
          <div className="sticky top-[60px] space-y-[12px]">
            {/* External links card */}
            <div className="rounded-[6px] bg-white p-[16px] shadow-[0_1px_4px_rgba(0,0,0,0.06)]">
              <h4 className="mb-[10px] text-[13px] font-bold text-[#333]">外部链接</h4>
              <div className="space-y-[8px]">
                <a
                  href={`https://tieba.baidu.com/f?kw=${encodeURIComponent(forumName)}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-[6px] rounded-[4px] border border-[#e8e8e8] px-[10px] py-[8px] text-[13px] text-[#333] hover:border-[#4096ff] hover:text-[#4096ff]"
                >
                  <span className="text-[16px]">🔗</span>
                  百度贴吧 - {forumName}吧
                </a>
                <a
                  href={`https://tieba.baidu.com/f?kw=${encodeURIComponent(forumName)}&ie=utf-8&tab=good`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-[6px] rounded-[4px] border border-[#e8e8e8] px-[10px] py-[8px] text-[13px] text-[#333] hover:border-[#4096ff] hover:text-[#4096ff]"
                >
                  <span className="text-[16px]">⭐</span>
                  精品区
                </a>
                <a
                  href={`https://tieba.baidu.com/bawu2/platform/listBawuTeamInfo?word=${encodeURIComponent(forumName)}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-[6px] rounded-[4px] border border-[#e8e8e8] px-[10px] py-[8px] text-[13px] text-[#333] hover:border-[#4096ff] hover:text-[#4096ff]"
                >
                  <span className="text-[16px]">👥</span>
                  吧务团队
                </a>
              </div>
            </div>

            {/* Archive stats */}
            {forum && (
              <div className="rounded-[6px] bg-white p-[16px] shadow-[0_1px_4px_rgba(0,0,0,0.06)]">
                <h4 className="mb-[10px] text-[13px] font-bold text-[#333]">归档统计</h4>
                <div className="space-y-[6px] text-[13px]">
                  <div className="flex items-center justify-between">
                    <span className="text-[#666]">归档帖子</span>
                    <span className="font-bold text-[#222]">{forum.archived_threads}</span>
                  </div>
                  {forum.media_files > 0 && (
                    <div className="flex items-center justify-between">
                      <span className="text-[#666]">媒体文件</span>
                      <span className="font-bold text-[#222]">{forum.media_files}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Back to top */}
            <button
              type="button"
              onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
              className="w-full rounded-[6px] bg-white py-[10px] text-center text-[13px] font-medium text-[#555] shadow-[0_1px_4px_rgba(0,0,0,0.06)] hover:text-[#4096ff]"
            >
              ↑ 回到顶部
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function formatNum(n: number): string {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

function formatDate(ts: number): string {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  if (d.getFullYear() === now.getFullYear()) {
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function generatePageNumbers(current: number, total: number): (number | string)[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages: (number | string)[] = [1]
  if (current > 3) pages.push('...')
  for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
    pages.push(i)
  }
  if (current < total - 2) pages.push('...')
  pages.push(total)
  return pages
}
