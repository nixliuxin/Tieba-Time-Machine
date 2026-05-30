import { useState } from 'react'
import type { Post, UserInfo } from '@/lib/api'
import { getMediaUrl } from '@/lib/api'
import { ContentRenderer } from './content-renderer'

const TIEBA_USER_URL = 'https://tieba.baidu.com/home/main'
const TIEBA_POST_URL = 'https://tieba.baidu.com/p'

export function PostCard({
  post,
  users,
  subPosts,
  forumName,
  mediaFiles,
  tid,
}: {
  post: Post
  users: Record<string, UserInfo>
  subPosts?: Post[]
  forumName: string
  mediaFiles: string[]
  tid: number
}) {
  const user = findUser(post.user_id, users)
  const avatarUrl = user?.avatar
    ? getMediaUrl(forumName, `${tid}/user_avatar/${user.avatar}`)
    : undefined

  const userPageUrl = user?.portrait
    ? `${TIEBA_USER_URL}?id=${user.portrait}`
    : undefined

  return (
    <div className="flex border-b border-[#e4e6eb] last:border-b-0">
      {/* Left user panel - like original Tieba */}
      <div className="w-[120px] shrink-0 border-r border-[#f0f0f0] px-[10px] py-[16px] text-center">
        {/* Avatar */}
        <a href={userPageUrl} target="_blank" rel="noreferrer" className="inline-block">
          {avatarUrl ? (
            <img
              src={avatarUrl}
              alt=""
              className="mx-auto h-[75px] w-[75px] rounded-[4px] border border-[#e0e0e0] object-cover"
              loading="lazy"
            />
          ) : (
            <div className="mx-auto flex h-[75px] w-[75px] items-center justify-center rounded-[4px] bg-[#eef1f5] text-[24px] font-bold text-[#8590a6]">
              {user?.nickname?.[0] || '?'}
            </div>
          )}
        </a>

        {/* Username */}
        <a
          href={userPageUrl}
          target="_blank"
          rel="noreferrer"
          className="mt-[8px] block truncate text-[12px] font-medium text-[#2d64b3] hover:underline"
        >
          {user?.nickname || user?.username || '匿名'}
        </a>

        {/* Level badge */}
        {user && Number(user.level) > 0 && (
          <div className="mt-[4px] flex items-center justify-center gap-[2px]">
            <span className="inline-flex h-[14px] items-center rounded-[2px] bg-[#ffd43b] px-[4px] text-[9px] font-bold text-[#5c3d00]">
              Lv.{user.level}
            </span>
          </div>
        )}

        {/* Gender */}
        {user && Number(user.gender) > 0 && (
          <div className="mt-[2px] text-[11px]">
            {user.gender === 1 ? <span className="text-[#4096ff]">♂</span> : <span className="text-[#ff6b81]">♀</span>}
          </div>
        )}
      </div>

      {/* Right content panel */}
      <div className="min-w-0 flex-1 px-[16px] py-[16px]">
        {/* Thread author badge */}
        {!!post.is_thread_author && (
          <span className="mb-[6px] inline-flex h-[18px] items-center rounded-[2px] bg-[#6c5ce7] px-[6px] text-[10px] font-bold text-white">
            楼主
          </span>
        )}

        {/* Post content */}
        <div className="text-[15px] leading-[28px] text-[#222] [white-space:pre-wrap]">
          <ContentRenderer contents={post.contents} forumName={forumName} mediaFiles={mediaFiles} />
        </div>

        {/* Post footer - mimics original Tieba */}
        <div className="mt-[16px] flex items-center border-t border-[#f5f5f5] pt-[10px] text-[12px] text-[#666]">
          <div className="flex items-center gap-[16px]">
            {user?.ip && <span>IP属地: {user.ip}</span>}
            <span>{post.floor}楼</span>
            <span>{formatTime(post.create_time)}</span>
            {Number(post.agree) > 0 && <span>👍 {post.agree}</span>}
          </div>
          <div className="ml-auto flex items-center gap-[8px]">
            <a
              href={`${TIEBA_POST_URL}/${tid}?pn=1#post_content_${post.id}`}
              target="_blank"
              rel="noreferrer"
              className="rounded-[3px] border border-[#4096ff] px-[8px] py-[2px] text-[11px] font-medium text-[#4096ff] hover:bg-[#4096ff] hover:text-white"
            >
              原帖 ↗
            </a>
          </div>
        </div>

        {/* Sub-posts (楼中楼) */}
        {Array.isArray(subPosts) && subPosts.length > 0 && (
          <CommentList
            subPosts={subPosts}
            users={users}
            forumName={forumName}
            mediaFiles={mediaFiles}
            tid={tid}
          />
        )}
      </div>
    </div>
  )
}

function CommentList({
  subPosts,
  users,
  forumName,
  mediaFiles,
  tid,
}: {
  subPosts: Post[]
  users: Record<string, UserInfo>
  forumName: string
  mediaFiles: string[]
  tid: number
}) {
  const [expanded, setExpanded] = useState(subPosts.length <= 5)
  const visible = expanded ? subPosts : subPosts.slice(0, 3)

  return (
    <div className="mt-[12px] rounded-[4px] border border-[#f0f0f0] bg-[#fafbfc]">
      {visible.map((sp) => {
        const spUser = findUser(sp.user_id, users)
        const spAvatar = spUser?.avatar
          ? getMediaUrl(forumName, `${tid}/user_avatar/${spUser.avatar}`)
          : undefined
        const spUserUrl = spUser?.portrait
          ? `${TIEBA_USER_URL}?id=${spUser.portrait}`
          : undefined

        return (
          <div key={sp.id} className="flex border-b border-[#f0f0f0] px-[12px] py-[10px] last:border-b-0">
            {/* Small avatar */}
            <a href={spUserUrl} target="_blank" rel="noreferrer" className="mr-[10px] shrink-0">
              {spAvatar ? (
                <img
                  src={spAvatar}
                  alt=""
                  className="h-[32px] w-[32px] rounded-[3px] border border-[#e0e0e0] object-cover"
                  loading="lazy"
                />
              ) : (
                <div className="flex h-[32px] w-[32px] items-center justify-center rounded-[3px] bg-[#eef1f5] text-[11px] font-bold text-[#8590a6]">
                  {spUser?.nickname?.[0] || '?'}
                </div>
              )}
            </a>

            {/* Comment body */}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-[4px]">
                <a
                  href={spUserUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[13px] font-bold text-[#2d64b3] hover:underline"
                >
                  {spUser?.nickname || '匿名'}
                </a>
                {!!sp.is_thread_author && (
                  <span className="inline-flex h-[14px] items-center rounded-[2px] bg-[#6c5ce7] px-[4px] text-[9px] font-bold text-white">
                    楼主
                  </span>
                )}
                <span className="ml-auto text-[11px] text-[#999]">{formatTime(sp.create_time)}</span>
              </div>
              <div className="mt-[4px] text-[14px] leading-[24px] text-[#333]">
                <ContentRenderer contents={sp.contents} forumName={forumName} mediaFiles={mediaFiles} />
              </div>
              {Number(sp.agree) > 0 && (
                <div className="mt-[2px] text-[11px] text-[#999]">👍 {sp.agree}</div>
              )}
            </div>
          </div>
        )
      })}

      {!expanded && subPosts.length > 3 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="block w-full py-[8px] text-center text-[13px] font-medium text-[#4096ff] hover:bg-[#f5f7fa]"
        >
          查看全部 {subPosts.length} 条回复 →
        </button>
      )}
    </div>
  )
}

function findUser(userId: number, users: Record<string, UserInfo>): UserInfo | undefined {
  if (!userId) return undefined
  return users[String(userId)] || Object.values(users).find((u) => (u as any).user_id === userId)
}

function formatTime(ts: number): string {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const now = new Date()
  const diff = now.getTime() - d.getTime()

  if (diff < 60_000) return '刚刚'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}分钟前`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}小时前`
  if (d.getFullYear() === now.getFullYear()) {
    return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
