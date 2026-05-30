import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface SectionProps {
  children: ReactNode
  className?: string
  gap?: boolean
  id?: string
  removeTopSpacing?: boolean
  spacing?: 'tight' | 'default' | 'loose' | 'generous' | 'spacious'
}

function Section({
  children,
  className,
  id,
  spacing = 'default',
  removeTopSpacing = true,
  gap = true,
}: SectionProps) {
  const paddingClasses = {
    tight: 'py-8',
    default: 'py-16',
    loose: 'py-16 md:py-20',
    generous: 'py-20 sm:py-28 md:py-32',
    spacious: 'py-24 sm:py-32 md:py-40',
  }

  const gapClasses = {
    tight: 'space-y-4',
    default: 'space-y-6',
    loose: 'space-y-8',
    generous: 'space-y-6',
    spacious: 'space-y-8',
  }

  return (
    <div
      className={cn(
        paddingClasses[spacing],
        gap && gapClasses[spacing],
        removeTopSpacing && 'pt-0 md:pt-0',
        className
      )}
      id={id}
    >
      {children}
    </div>
  )
}

export { Section }
export default Section
