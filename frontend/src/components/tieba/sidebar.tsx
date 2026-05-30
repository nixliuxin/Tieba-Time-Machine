import type { Forum } from '@/lib/api'

const TIEBA_FORUM_URL = 'https://tieba.baidu.com/f'

export function ThreadSidebar({
  forum,
  threadMeta,
  collapsed,
  onToggle,
}: {
  forum?: Forum
  threadMeta?: {
    create_time: number
    reply_num: number
    view_num: number
    agree: number
  }
  collapsed: boolean
  onToggle: () => void
}) {
  return (
    <>
      {/* Sidebar panel */}
      <aside
        className={`shrink-0 transition-all duration-300 ${
          collapsed
            ? 'w-0 overflow-hidden opacity-0'
            : 'sticky top-0 h-screen w-[260px] overflow-y-auto border-r border-[#e8e8e8] bg-[#fafbfc]'
        }`}
      >
        <div className="p-[16px]">
          {/* Forum info section */}
          {forum && (
            <div className="mb-[16px] rounded-[6px] bg-white p-[14px] shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
              {/* Forum name + icon */}
              <div className="mb-[10px] flex items-center gap-[8px]">
                <div className="flex h-[36px] w-[36px] shrink-0 items-center justify-center rounded-[4px] bg-[#4096ff] text-[14px] font-bold text-white">
                  {forum.forum_name[0]}
                </div>
                <div className="min-w-0">
                  <div className="truncate text-[14px] font-bold text-[#333]">{forum.forum_name}吧</div>
                  <a
                    href={`${TIEBA_FORUM_URL}?kw=${encodeURIComponent(forum.forum_name)}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[11px] text-[#c0c4cc] hover:text-[#4096ff]"
                  >
                    百度贴吧 ↗
                  </a>
                </div>
              </div>

              {/* Stats grid */}
              <div className="grid grid-cols-2 gap-[8px] text-center">
                {forum.member_num > 0 && (
                  <div className="rounded-[4px] bg-[#f5f7fa] py-[6px]">
                    <div className="text-[14px] font-bold text-[#222]">{formatNum(forum.member_num)}</div>
                    <div className="text-[10px] text-[#777]">关注</div>
                  </div>
                )}
                {forum.thread_num > 0 && (
                  <div className="rounded-[4px] bg-[#f5f7fa] py-[6px]">
                    <div className="text-[14px] font-bold text-[#222]">{formatNum(forum.thread_num)}</div>
                    <div className="text-[10px] text-[#777]">主题</div>
                  </div>
                )}
                {forum.post_num > 0 && (
                  <div className="rounded-[4px] bg-[#f5f7fa] py-[6px]">
                    <div className="text-[14px] font-bold text-[#222]">{formatNum(forum.post_num)}</div>
                    <div className="text-[10px] text-[#777]">帖子</div>
                  </div>
                )}
                <div className="rounded-[4px] bg-[#f5f7fa] py-[6px]">
                  <div className="text-[14px] font-bold text-[#222]">{forum.archived_threads}</div>
                  <div className="text-[10px] text-[#777]">已归档</div>
                </div>
              </div>

              {forum.slogan && (
                <div className="mt-[10px] rounded-[4px] bg-[#f5f7fa] px-[10px] py-[8px] text-[12px] leading-[18px] text-[#666]">
                  {forum.slogan}
                </div>
              )}
            </div>
          )}

          {/* Thread meta section */}
          {threadMeta && (
            <div className="rounded-[6px] bg-white p-[14px] shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
              <h4 className="mb-[10px] text-[13px] font-bold text-[#333]">本帖信息</h4>
              <div className="space-y-[8px] text-[12px]">
                <div className="flex items-center justify-between">
                  <span className="text-[#666]">发帖时间</span>
                  <span className="font-medium text-[#222]">
                    {threadMeta.create_time
                      ? new Date(threadMeta.create_time * 1000).toLocaleDateString('zh-CN')
                      : '-'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#666]">浏览量</span>
                  <span className="font-medium text-[#222]">{threadMeta.view_num.toLocaleString()}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#666]">回复数</span>
                  <span className="font-medium text-[#222]">{threadMeta.reply_num}</span>
                </div>
                {Number(threadMeta.agree) > 0 && (
                  <div className="flex items-center justify-between">
                    <span className="text-[#666]">点赞</span>
                    <span className="font-medium text-[#222]">{threadMeta.agree}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Collapse button at bottom */}
          <button
            type="button"
            onClick={onToggle}
            className="mt-[16px] w-full rounded-[4px] border border-[#e8e8e8] py-[6px] text-center text-[12px] text-[#9499A0] hover:border-[#4096ff] hover:text-[#4096ff]"
          >
            收起侧栏
          </button>
        </div>
      </aside>

      {/* Expand button when collapsed */}
      {collapsed && (
        <button
          type="button"
          onClick={onToggle}
          className="sticky top-[50%] z-30 flex h-[60px] w-[20px] -translate-y-1/2 items-center justify-center rounded-r-[4px] border border-l-0 border-[#e8e8e8] bg-[#fafbfc] text-[12px] text-[#9499A0] hover:bg-[#f0f2f5] hover:text-[#4096ff]"
          title="展开侧栏"
        >
          ▶
        </button>
      )}
    </>
  )
}

function formatNum(n: number): string {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}
