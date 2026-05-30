import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

type MaxWidth = 'fluid' | 'wider' | 'wide' | 'default' | 'narrow' | 'narrower' | 'narrowest'
type Padding = 'all' | 'x' | 'none'

interface ContainerProps {
  children: ReactNode
  className?: string
  /** Max width variant */
  maxWidth?: MaxWidth
  /** Padding: 'all' (p-6) | 'x' (px-6) | 'none' (p-0) */
  padding?: Padding
}

const maxWidthStyles: Record<MaxWidth, string> = {
  fluid: 'max-w-full',
  wider: 'max-w-8xl',
  wide: 'max-w-5xl',
  default: 'max-w-7xl',
  narrow: 'max-w-4xl',
  narrower: 'max-w-2xl',
  narrowest: 'max-w-xl',
}

const paddingStyles: Record<Padding, string> = {
  all: 'p-6',
  x: 'px-6',
  none: 'p-0',
}

const Container = ({
  children,
  maxWidth = 'default',
  padding = 'all',
  className,
}: ContainerProps) => {
  return (
    <div
      className={cn(
        'container mx-auto flex min-w-0 flex-col gap-8',
        maxWidthStyles[maxWidth],
        paddingStyles[padding],
        className
      )}
    >
      {children}
    </div>
  )
}

export default Container
