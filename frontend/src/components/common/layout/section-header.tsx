import { cn } from '@/lib/utils'

interface SectionHeaderProps {
  actions?: React.ReactNode
  align?: 'left' | 'center' | 'right'
  className?: string
  description?: string
  descriptionClassName?: string
  padding?: 'none' | 'tight' | 'default' | 'loose'
  title: React.ReactNode
  titleClassName?: string
  variant?: 'display' | 'primary' | 'secondary' | 'muted' | 'subtle'
}

export function SectionHeader({
  actions,
  title,
  description,
  className,
  titleClassName,
  descriptionClassName,
  variant = 'primary',
  align = 'left',
  padding = 'default',
}: SectionHeaderProps) {
  const paddingClasses = {
    none: '',
    tight: 'py-4 sm:py-6 md:py-8',
    default: 'py-8 sm:py-16 md:py-20',
    loose: 'py-12 sm:py-20 md:py-28',
  }

  const variantConfig = {
    display: {
      TitleTag: 'h1' as const,
      DescTag: 'p' as const,
      titleClass: 'font-extrabold text-7xl leading-none tracking-tight text-balance max-w-4xl',
      descClass: 'mt-6 max-w-2xl text-xl leading-relaxed text-balance text-muted-foreground',
      withPadding: true,
    },
    primary: {
      TitleTag: 'h1' as const,
      DescTag: 'p' as const,
      titleClass: 'font-extrabold text-6xl leading-none tracking-tight text-balance max-w-3xl',
      descClass: 'mt-6 max-w-2xl text-xl leading-relaxed text-balance text-muted-foreground',
      withPadding: false,
    },
    secondary: {
      TitleTag: 'h2' as const,
      DescTag: 'p' as const,
      titleClass: 'font-extrabold text-5xl leading-none tracking-tight text-balance max-w-2xl',
      descClass: 'mt-6 max-w-sm text-lg leading-relaxed text-balance text-muted-foreground',
      withPadding: false,
    },
    muted: {
      TitleTag: 'h3' as const,
      DescTag: 'p' as const,
      titleClass: 'font-bold text-4xl leading-tight tracking-tight text-balance',
      descClass: 'mt-2 max-w-lg text-base leading-relaxed text-muted-foreground',
      withPadding: false,
    },
    subtle: {
      TitleTag: 'h4' as const,
      DescTag: 'p' as const,
      titleClass: 'font-semibold text-2xl leading-snug tracking-tight',
      descClass: 'mt-1.5 max-w-md text-sm leading-relaxed text-muted-foreground/80',
      withPadding: false,
    },
  }

  const config = variantConfig[variant]
  const { TitleTag, DescTag, titleClass, descClass, withPadding } = config

  const alignClasses = {
    center: 'mx-auto text-center',
    right: 'ml-auto text-right',
    left: '',
  }

  const actionsAlignClass = {
    center: 'justify-center',
    right: 'justify-end',
    left: 'justify-start',
  }

  const content = (
    <>
      <TitleTag className={cn(titleClass, alignClasses[align], titleClassName)}>{title}</TitleTag>
      {description && (
        <DescTag className={cn(descClass, alignClasses[align], descriptionClassName)}>
          {description}
        </DescTag>
      )}
      {actions && (
        <div className={cn('mt-8 flex flex-wrap gap-3', actionsAlignClass[align])}>{actions}</div>
      )}
    </>
  )

  const renderContent = () =>
    withPadding ? <div className={cn(paddingClasses[padding])}>{content}</div> : content

  return (
    <div
      className={cn(
        align === 'center' && 'text-center',
        align === 'right' && 'text-right',
        className
      )}
    >
      {renderContent()}
    </div>
  )
}
