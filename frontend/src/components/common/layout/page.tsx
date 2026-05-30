import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface PageProps {
  children: ReactNode
  className?: string
  noPadding?: boolean
}

const Page = ({ children, className, noPadding = false }: PageProps) => {
  return (
    <div className={cn('min-h-full', !noPadding && 'pt-8 pb-20', className)} id="page">
      {children}
    </div>
  )
}

export default Page
