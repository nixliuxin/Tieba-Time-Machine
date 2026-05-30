import { useQuery } from '@tanstack/react-query'
import { Link, useSearch } from '@tanstack/react-router'
import { getThreads } from '@/lib/api'

export default function SearchPage() {
  const searchParams = useSearch({ strict: false }) as { q?: string; page?: string }
  const q = searchParams.q || ''
  const page = Number(searchParams.page) || 1

  const { data, isLoading } = useQuery({
    queryKey: ['search', q, page],
    queryFn: () => getThreads({ q, page }),
    enabled: !!q,
  })

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0

  return (
    <div className="min-h-screen bg-[#f0f2f5]">
      {/* Header */}
      <div className="border-b border-[#e8e8e8] bg-white px-[20px] py-[12px]">
        <div className="mx-auto flex max-w-[900px] items-center gap-[16px]">
          <Link to="/" className="text-[13px] text-[#9499A0] hover:text-[#4096ff]">
            ← 首页
          </Link>
          <form className="flex-1" action="/search">
            <input
              type="text"
              name="q"
              defaultValue={q}
              placeholder="搜索帖子内容..."
              className="w-full rounded-[4px] border border-[#dcdfe6] bg-[#f8f9fa] px-[12px] py-[8px] text-[14px] placeholder:text-[#c0c4cc] focus:border-[#4096ff] focus:outline-none"
            />
          </form>
        </div>
      </div>

      <div className="mx-auto max-w-[900px] px-[20px] py-[20px]">
        {/* Result info */}
        {q && data && (
          <div className="mb-[16px] text-[13px] text-[#9499A0]">
            搜索 "{q}" — 找到 {data.total} 条结果
          </div>
        )}

        {isLoading && <div className="py-[60px] text-center text-[#9499A0]">搜索中...</div>}

        {!q && (
          <div className="py-[60px] text-center text-[#9499A0]">输入关键词开始搜索</div>
        )}

        {/* Results */}
        {data && data.items.length > 0 && (
          <div className="space-y-[8px]">
            {data.items.map((item) => (
              <Link
                key={item.tid}
                to="/threads/$tid"
                params={{ tid: String(item.tid) }}
                className="block rounded-[4px] bg-white p-[16px] shadow-sm hover:shadow-md"
              >
                <h3 className="text-[15px] font-medium text-[#18191C]">
                  {item.title || `[tid: ${item.tid}]`}
                </h3>
                {item.snippet && (
                  <p
                    className="mt-[6px] text-[13px] leading-[20px] text-[#666]"
                    dangerouslySetInnerHTML={{ __html: item.snippet }}
                  />
                )}
                <div className="mt-[8px] flex gap-[16px] text-[12px] text-[#9499A0]">
                  <span>{item.forum_name}吧</span>
                  <span>{formatTime(item.create_time)}</span>
                  <span>回复 {item.reply_num}</span>
                </div>
              </Link>
            ))}
          </div>
        )}

        {data && data.items.length === 0 && q && (
          <div className="py-[60px] text-center text-[#9499A0]">未找到相关结果</div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="mt-[20px] flex items-center justify-center gap-[8px] text-[13px]">
            {page > 1 && (
              <Link
                to="/search"
                search={{ q, page: page - 1 }}
                className="inline-flex h-[32px] items-center rounded-[4px] border border-[#dcdfe6] bg-white px-[12px] text-[#606266] hover:border-[#4096ff] hover:text-[#4096ff]"
              >
                上一页
              </Link>
            )}
            <span className="text-[#9499A0]">第 {page}/{totalPages} 页</span>
            {page < totalPages && (
              <Link
                to="/search"
                search={{ q, page: page + 1 }}
                className="inline-flex h-[32px] items-center rounded-[4px] border border-[#dcdfe6] bg-white px-[12px] text-[#606266] hover:border-[#4096ff] hover:text-[#4096ff]"
              >
                下一页
              </Link>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function formatTime(ts: number): string {
  if (!ts) return ''
  return new Date(ts * 1000).toLocaleDateString('zh-CN')
}
