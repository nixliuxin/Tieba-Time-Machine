import { useState, useRef } from 'react'
import type { UserInfo } from '@/lib/api'
import { getMediaUrl } from '@/lib/api'

export function UserPopover({
  user,
  forumName,
  tid,
  children,
}: {
  user: UserInfo | undefined
  forumName: string
  tid?: number
  children: React.ReactNode
}) {
  const [show, setShow] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  if (!user) return <>{children}</>

  const handleEnter = () => {
    timerRef.current = setTimeout(() => setShow(true), 300)
  }

  const handleLeave = () => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setShow(false)
  }

  const avatarUrl = user.avatar && tid
    ? getMediaUrl(forumName, `${tid}/user_avatar/${user.avatar}`)
    : undefined

  return (
    <div className="relative inline-block" onMouseEnter={handleEnter} onMouseLeave={handleLeave}>
      {children}
      {show && (
        <div className="absolute left-0 top-full z-50 mt-[4px] w-[240px] rounded-[4px] border border-[#e8e8e8] bg-white p-[16px] shadow-[0_4px_12px_rgba(0,0,0,0.1)]">
          <div className="flex items-center gap-[10px]">
            {avatarUrl ? (
              <img src={avatarUrl} alt="" className="h-[40px] w-[40px] rounded-[4px] border border-[#e0e0e0] object-cover" />
            ) : (
              <div className="flex h-[40px] w-[40px] items-center justify-center rounded-[4px] bg-[#eef1f5] text-[14px] font-bold text-[#8590a6]">
                {(user.nickname || user.username || '?')[0]}
              </div>
            )}
            <div className="min-w-0">
              <div className="truncate text-[14px] font-medium text-[#2d64b3]">{user.nickname || user.username}</div>
              {user.username && user.username !== user.nickname && (
                <div className="truncate text-[12px] text-[#9499A0]">@{user.username}</div>
              )}
            </div>
          </div>
          <div className="mt-[10px] flex flex-wrap gap-x-[12px] gap-y-[4px] text-[12px] text-[#9499A0]">
            {user.level > 0 && (
              <span className="inline-flex items-center gap-[2px]">
                <span className="inline-flex h-[14px] items-center rounded-[3px] bg-[#FBD279] px-[4px] text-[10px] font-bold text-[#593617]">
                  Lv.{user.level}
                </span>
              </span>
            )}
            {user.gender > 0 && <span>{user.gender === 1 ? '男' : '女'}</span>}
            {user.ip && <span>IP属地: {user.ip}</span>}
            {user.is_vip && <span className="text-[#f60]">VIP</span>}
          </div>
        </div>
      )}
    </div>
  )
}
