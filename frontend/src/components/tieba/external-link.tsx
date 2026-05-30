/**
 * Unified external link button style for all links to tieba.baidu.com.
 * Provides consistent visual identity across the app.
 */
export function ExternalLink({
  href,
  children,
  variant = 'default',
  className = '',
}: {
  href: string
  children: React.ReactNode
  variant?: 'default' | 'primary' | 'inline'
  className?: string
}) {
  const baseStyles = 'inline-flex items-center gap-[4px] no-underline transition-all'
  const variants = {
    default:
      'rounded-[3px] border border-[#4096ff] bg-white px-[8px] py-[3px] text-[12px] font-medium text-[#4096ff] hover:bg-[#4096ff] hover:text-white',
    primary:
      'rounded-[3px] bg-[#4096ff] px-[10px] py-[4px] text-[12px] font-medium text-white hover:bg-[#1677ff]',
    inline:
      'text-[12px] text-[#4096ff] hover:underline',
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={`${baseStyles} ${variants[variant]} ${className}`}
    >
      {children}
      <span className="text-[10px] opacity-70">↗</span>
    </a>
  )
}

export function TiebaForumLink({ forumName, variant = 'default', className = '' }: { forumName: string; variant?: 'default' | 'primary' | 'inline'; className?: string }) {
  return (
    <ExternalLink href={`https://tieba.baidu.com/f?kw=${encodeURIComponent(forumName)}`} variant={variant} className={className}>
      百度贴吧
    </ExternalLink>
  )
}

export function TiebaPostLink({ tid, variant = 'default', className = '' }: { tid: number; variant?: 'default' | 'primary' | 'inline'; className?: string }) {
  return (
    <ExternalLink href={`https://tieba.baidu.com/p/${tid}`} variant={variant} className={className}>
      查看原帖
    </ExternalLink>
  )
}

export function TiebaUserLink({ portrait, nickname, variant = 'inline', className = '' }: { portrait: string; nickname?: string; variant?: 'default' | 'primary' | 'inline'; className?: string }) {
  return (
    <ExternalLink href={`https://tieba.baidu.com/home/main?id=${portrait}`} variant={variant} className={className}>
      {nickname || '用户主页'}
    </ExternalLink>
  )
}
