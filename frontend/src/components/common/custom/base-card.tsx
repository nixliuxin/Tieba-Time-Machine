import { ArrowUpRight } from 'lucide-react'
import { AnimatePresence, motion, useMotionValue } from 'motion/react'
import { useCallback, useRef, useState } from 'react'

import { type AspectRatio, Image } from '@/components/ui/image'
import { cn } from '@/lib/utils'

/* -----------------------------------------------------------------------------
 * Card - Root container
 * -------------------------------------------------------------------------- */

interface CardProps extends React.ComponentProps<'div'> {
  /** Custom icon for cursor label */
  cursorIcon?: React.ReactNode
  /** Cursor label text (shows a following badge on hover) */
  cursorLabel?: string
  /** Padding size */
  padding?: 'none' | 'sm' | 'md' | 'lg'
  /** Card variant for different use cases */
  variant?: 'default' | 'interactive' | 'ghost'
}

function Card({
  className,
  variant = 'default',
  padding = 'md',
  cursorLabel,
  cursorIcon,
  children,
  ...props
}: CardProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const rectRef = useRef<DOMRect | null>(null)
  const [cursorActive, setCursorActive] = useState(false)

  const cursorX = useMotionValue(0)
  const cursorY = useMotionValue(0)

  const handlePointerEnter = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!containerRef.current) {
        return
      }
      rectRef.current = containerRef.current.getBoundingClientRect()
      cursorX.jump(e.clientX - rectRef.current.left)
      cursorY.jump(e.clientY - rectRef.current.top)
      setCursorActive(true)
    },
    [cursorX, cursorY]
  )

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!rectRef.current) {
        return
      }
      cursorX.set(e.clientX - rectRef.current.left)
      cursorY.set(e.clientY - rectRef.current.top)
    },
    [cursorX, cursorY]
  )

  const handlePointerLeave = useCallback(() => {
    rectRef.current = null
    setCursorActive(false)
  }, [])

  return (
    <div
      className={cn(
        'group relative flex flex-col text-card-foreground',
        // Ghost variant — no bg/border, pseudo-element hover bg
        variant === 'ghost'
          ? 'isolate before:pointer-events-none before:absolute before:-inset-1 before:-z-[1] before:scale-[0.9] before:rounded-2xl before:bg-accent/50 before:opacity-0 before:transition-all before:duration-200 before:ease-out hover:before:scale-100 hover:before:opacity-100 active:before:scale-[0.97]'
          : 'overflow-hidden rounded-3xl border bg-card',
        // Padding variants (no gap - children handle their own padding/spacing)
        padding === 'none' && 'p-0',
        padding === 'sm' && 'p-1',
        padding === 'md' && 'p-1.5',
        padding === 'lg' && 'p-3',
        // Interactive variant - lift + shadow + scale
        variant === 'interactive' &&
          'cursor-pointer transition-all duration-300 ease-out hover:-translate-y-1 hover:border-border/80 hover:shadow-black/5 hover:shadow-lg',
        // Hide cursor when label is active
        cursorLabel && cursorActive && 'cursor-none',
        className
      )}
      data-slot="card"
      onPointerEnter={cursorLabel ? handlePointerEnter : undefined}
      onPointerLeave={cursorLabel ? handlePointerLeave : undefined}
      onPointerMove={cursorLabel ? handlePointerMove : undefined}
      ref={containerRef}
      {...props}
    >
      {children}

      {/* Cursor label — 1:1 tracking via motion values, zero re-renders during movement */}
      <AnimatePresence>
        {cursorLabel && cursorActive && (
          <motion.div
            animate={{ scale: 1, opacity: 1 }}
            className="pointer-events-none absolute z-50 flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full bg-foreground px-2 py-1 font-medium text-background text-xs shadow-lg"
            exit={{ scale: 0, opacity: 0 }}
            initial={{ scale: 0, opacity: 0 }}
            style={{
              left: cursorX,
              top: cursorY,
              x: '-50%',
              y: '-50%',
            }}
            transition={{ type: 'spring', stiffness: 400, damping: 25 }}
          >
            {cursorIcon || <ArrowUpRight className="size-3" />}
            {cursorLabel}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/* -----------------------------------------------------------------------------
 * CardHeader - Top layout holder (for leading label, badges, actions)
 * -------------------------------------------------------------------------- */

interface CardHeaderProps extends React.ComponentProps<'div'> {
  /** Padding inside header */
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

function CardHeader({ className, padding = 'md', ...props }: CardHeaderProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-between gap-1',
        padding === 'none' && 'p-0',
        padding === 'sm' && 'p-3',
        padding === 'md' && 'p-4',
        padding === 'lg' && 'p-5',
        className
      )}
      data-slot="card-header"
      {...props}
    />
  )
}

/* -----------------------------------------------------------------------------
 * CardLabel - Leading label text (e.g., "Leading Label")
 * -------------------------------------------------------------------------- */

function CardLabel({ className, ...props }: React.ComponentProps<'span'>) {
  return (
    <span className={cn('text-foreground text-sm', className)} data-slot="card-label" {...props} />
  )
}

/* -----------------------------------------------------------------------------
 * CardThumbnail - Image with aspect ratio options
 * -------------------------------------------------------------------------- */

const ASPECT_RATIO_SIZES: Partial<Record<AspectRatio, [number, number]>> = {
  '1/1': [1, 1],
  '4/3': [4, 3],
  '3/4': [3, 4],
  '16/9': [16, 9],
  '9/16': [9, 16],
  '2/3': [2, 3],
  '3/2': [3, 2],
  '5/4': [5, 4],
  '21/9': [21, 9],
  '9/21': [9, 21],
}

const ASPECT_RATIO_CLASSES: Record<AspectRatio, string> = {
  auto: '',
  '1/1': 'aspect-square',
  '4/3': 'aspect-[4/3]',
  '3/4': 'aspect-[3/4]',
  '16/9': 'aspect-video',
  '9/16': 'aspect-[9/16]',
  '2/3': 'aspect-[2/3]',
  '3/2': 'aspect-[3/2]',
  '5/4': 'aspect-[5/4]',
  '21/9': 'aspect-[21/9]',
  '9/21': 'aspect-[9/21]',
}

interface CardThumbnailProps extends React.ComponentProps<'div'> {
  alt?: string
  aspectRatio?: AspectRatio
  /** Enable hover scale effect */
  hoverScale?: boolean
  /** Use native img instead of Image component */
  native?: boolean
  src?: string
}

function CardThumbnail({
  src,
  alt = 'Card thumbnail',
  aspectRatio = '16/9',
  hoverScale = true,
  native = false,
  className,
  ...props
}: CardThumbnailProps) {
  const aspectClass = ASPECT_RATIO_CLASSES[aspectRatio] ?? 'aspect-video'
  const hoverScaleClass = hoverScale
    ? 'transition-transform duration-300 group-hover:scale-105'
    : ''

  if (native) {
    return (
      <div
        className={cn(aspectClass, 'w-full overflow-hidden rounded-xl bg-muted/50', className)}
        data-slot="card-thumbnail"
        {...props}
      >
        {src && (
          <img
            alt={alt}
            className={cn('h-full w-full object-cover', hoverScaleClass)}
            height={ASPECT_RATIO_SIZES[aspectRatio]?.[1]}
            src={src}
            width={ASPECT_RATIO_SIZES[aspectRatio]?.[0]}
          />
        )}
      </div>
    )
  }

  return (
    <div
      className={cn('w-full overflow-hidden rounded-xl bg-muted/50', className)}
      data-slot="card-thumbnail"
      {...props}
    >
      <Image
        alt={alt}
        aspectRatio={aspectRatio}
        className={
          hoverScale
            ? '[&_div]:transition-transform [&_div]:duration-300 [&_div]:group-hover:scale-105'
            : ''
        }
        forceNoLazy
        src={src}
      />
    </div>
  )
}

/* -----------------------------------------------------------------------------
 * CardContent - Main text content area (title, subtitle, description, tags)
 * -------------------------------------------------------------------------- */

type ContentPaddingSize = 'none' | 'xs' | 'sm' | 'md' | 'lg'
type ResponsiveContentPadding =
  | ContentPaddingSize
  | { base?: ContentPaddingSize; sm?: ContentPaddingSize }

const CONTENT_PADDING: {
  base: Record<ContentPaddingSize, string>
  sm: Record<ContentPaddingSize, string>
} = {
  base: {
    none: 'p-0',
    xs: 'mt-1 gap-1 p-2',
    sm: 'gap-1 p-3',
    md: 'gap-2 p-4',
    lg: 'gap-3.5 p-5',
  },
  sm: {
    none: 'sm:mt-0 sm:p-0',
    xs: 'sm:mt-0 sm:gap-1 sm:p-2',
    sm: 'sm:mt-0 sm:gap-1 sm:p-3',
    md: 'sm:mt-0 sm:gap-2 sm:p-4',
    lg: 'sm:mt-0 sm:gap-3.5 sm:p-5',
  },
}

const FOOTER_PADDING: {
  base: Record<ContentPaddingSize, string>
  sm: Record<ContentPaddingSize, string>
} = {
  base: {
    none: 'p-0',
    xs: 'p-2 pt-0',
    sm: 'p-3 pt-0',
    md: 'p-4 pt-0',
    lg: 'p-5 pt-0',
  },
  sm: {
    none: 'sm:p-0',
    xs: 'sm:p-2 sm:pt-0',
    sm: 'sm:p-3 sm:pt-0',
    md: 'sm:p-4 sm:pt-0',
    lg: 'sm:p-5 sm:pt-0',
  },
}

function resolvePadding(
  padding: ResponsiveContentPadding,
  map: {
    base: Record<ContentPaddingSize, string>
    sm: Record<ContentPaddingSize, string>
  }
): string {
  if (typeof padding === 'string') {
    return map.base[padding]
  }
  const classes: string[] = []
  if (padding.base) {
    classes.push(map.base[padding.base])
  }
  if (padding.sm) {
    classes.push(map.sm[padding.sm])
  }
  return classes.join(' ')
}

interface CardContentProps extends React.ComponentProps<'div'> {
  /** Padding inside content area — string or responsive { base, sm } */
  padding?: ResponsiveContentPadding
}

function CardContent({ className, padding = 'md', ...props }: CardContentProps) {
  return (
    <div
      className={cn('flex flex-col gap-3', resolvePadding(padding, CONTENT_PADDING), className)}
      data-slot="card-content"
      {...props}
    />
  )
}

/* -----------------------------------------------------------------------------
 * CardTitle - Primary title text (Instrument Serif, 30px/38px)
 * -------------------------------------------------------------------------- */

interface CardTitleProps extends React.ComponentProps<'span'> {
  /** Line clamp for truncation */
  lineClamp?: 1 | 2 | 3
}

function CardTitle({ className, lineClamp = 2, ...props }: CardTitleProps) {
  return (
    <span
      className={cn(
        'font-bold text-foreground text-lg',
        lineClamp === 1 && 'line-clamp-1',
        lineClamp === 2 && 'line-clamp-2',
        lineClamp === 3 && 'line-clamp-3',
        className
      )}
      data-slot="card-title"
      {...props}
    />
  )
}

/* -----------------------------------------------------------------------------
 * CardDescription - Secondary descriptive text (14px/20px body text)
 * -------------------------------------------------------------------------- */

interface CardDescriptionProps extends React.ComponentProps<'span'> {
  /** Line clamp for truncation */
  lineClamp?: 1 | 2 | 3
}

function CardDescription({ className, lineClamp = 3, ...props }: CardDescriptionProps) {
  return (
    <span
      className={cn(
        'text-muted-foreground text-sm leading-5',
        lineClamp === 1 && 'line-clamp-1',
        lineClamp === 2 && 'line-clamp-2',
        lineClamp === 3 && 'line-clamp-3',
        className
      )}
      data-slot="card-description"
      {...props}
    />
  )
}

/* -----------------------------------------------------------------------------
 * CardTags - Container for tag badges
 * -------------------------------------------------------------------------- */

function CardTags({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      className={cn('flex flex-wrap items-center gap-1.5', className)}
      data-slot="card-tags"
      {...props}
    />
  )
}

/* -----------------------------------------------------------------------------
 * CardFooter - Bottom layout holder (for metadata, actions, buttons)
 * -------------------------------------------------------------------------- */

interface CardFooterProps extends React.ComponentProps<'div'> {
  /** Padding inside footer — string or responsive { base, sm } */
  padding?: ResponsiveContentPadding
}

function CardFooter({ className, padding = 'md', ...props }: CardFooterProps) {
  return (
    <div
      className={cn(
        'mt-auto flex items-center gap-2',
        resolvePadding(padding, FOOTER_PADDING),
        className
      )}
      data-slot="card-footer"
      {...props}
    />
  )
}

/* -----------------------------------------------------------------------------
 * CardAction - Action slot (positioned in header or footer)
 * -------------------------------------------------------------------------- */

function CardAction({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      className={cn('ml-auto flex items-center gap-2', className)}
      data-slot="card-action"
      {...props}
    />
  )
}

export {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardLabel,
  CardTags,
  CardThumbnail,
  CardTitle,
}
