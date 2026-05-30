import { cva, type VariantProps } from 'class-variance-authority'
import { forwardRef } from 'react'
import { ShineBorder } from '@/components/common/animated/shine-border'
import { cn } from '@/lib/utils'

const richButtonVariants = cva(
  [
    'relative inline-flex items-center justify-center gap-2 whitespace-nowrap',
    'font-medium transition-all duration-300 disabled:pointer-events-none disabled:opacity-50',
    'outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
    'group/rich-button cursor-pointer overflow-hidden text-primary-foreground',
    '[&_svg:not([class*="size-"])]:size-4 [&_svg]:pointer-events-none [&_svg]:shrink-0',
  ],
  {
    variants: {
      size: {
        sm: 'h-8 min-w-16 rounded-sm px-2 py-1 text-sm has-[>svg]:px-2.5',
        default: 'h-10 min-w-16 rounded-md px-3 py-1 text-base has-[>svg]:px-3',
        lg: 'h-10 rounded-lg px-6 text-lg has-[>svg]:px-4',
        icon: 'size-9',
        'icon-xs': "size-6 rounded-sm [&_svg:not([class*='size-'])]:size-3",
        'icon-sm': 'size-8 rounded-sm',
        'icon-lg': 'size-10',
      },
    },
    defaultVariants: {
      size: 'default',
    },
  }
)

interface RichButtonProps
  extends React.ComponentProps<'button'>,
    VariantProps<typeof richButtonVariants> {}

// Maps size variant to its radius token for concentric inner radii
const RADIUS_TOKEN: Record<string, string> = {
  sm: 'var(--radius-sm)',
  default: 'var(--radius-md)',
  lg: 'var(--radius-lg)',
  icon: 'var(--radius-md)',
  'icon-sm': 'var(--radius-sm)',
}

const RichButton = forwardRef<HTMLButtonElement, RichButtonProps>(
  ({ className, size, children, ...props }, ref) => {
    const radiusToken = className?.includes('rounded-full')
      ? 'var(--radius-full)'
      : RADIUS_TOKEN[size || 'default']

    // Inset lighting tuned for primary color
    const insetShadow = [
      'color-mix(in srgb, var(--color-white) 18%, transparent) 0px 1px 0.5px -0.5px inset',
      'color-mix(in srgb, var(--primary) 40%, transparent) 0px -2px 8px 2px inset',
      'color-mix(in srgb, var(--color-white) 48%, transparent) 0px -2px 8px 2px inset',
    ].join(', ')

    const primaryGlow = 'color-mix(in srgb, var(--primary) 40%, transparent) 0px 8px 24px -4px'
    const baseBoxShadow = `${insetShadow}, var(--shadow-lg), ${primaryGlow}`
    const hoverBoxShadow = `${insetShadow}, var(--shadow-2xl), ${primaryGlow}`
    const activeBoxShadow = `${insetShadow}, var(--shadow-xs), ${primaryGlow}`

    return (
      <button
        className={cn(richButtonVariants({ size }), className)}
        onMouseDown={(e: React.MouseEvent<HTMLButtonElement>) => {
          e.currentTarget.style.boxShadow = activeBoxShadow
          e.currentTarget.style.transform = 'translateY(1px)'
        }}
        onMouseEnter={(e: React.MouseEvent<HTMLButtonElement>) => {
          e.currentTarget.style.boxShadow = hoverBoxShadow
          e.currentTarget.style.transform = 'translateY(-1px)'
        }}
        onMouseLeave={(e: React.MouseEvent<HTMLButtonElement>) => {
          e.currentTarget.style.boxShadow = baseBoxShadow
          e.currentTarget.style.transform = 'translateY(0px)'
        }}
        onMouseUp={(e: React.MouseEvent<HTMLButtonElement>) => {
          e.currentTarget.style.boxShadow = hoverBoxShadow
          e.currentTarget.style.transform = 'translateY(-1px)'
        }}
        ref={ref}
        style={
          {
            '--_r': radiusToken,
            backgroundColor: 'var(--primary)',
            boxShadow: baseBoxShadow,
            transition: 'all 200ms ease, box-shadow 300ms ease',
          } as React.CSSProperties
        }
        {...props}
      >
        {/* Brightness/contrast gradient: bright top-left → deep bottom-right */}
        <div
          className="pointer-events-none absolute inset-0 rounded-[inherit]"
          style={{
            background: `
              linear-gradient(
                180deg,
                rgba(255,255,255,0.18) 0%,
                rgba(255,255,255,0.06) 40%,
                transparent 60%,
                rgba(0,0,0,0.16) 100%
              )
            `,
          }}
        />

        {/* Top-left highlight spot — intensifies on hover */}
        <div
          className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-50 transition-opacity duration-300 ease-out group-hover/rich-button:opacity-100"
          style={{
            background:
              'radial-gradient(ellipse 80% 100% at 50% 00%, rgba(255,255,255,1), transparent 70%)',
          }}
        />

        {/* Shine border — replaces static border ring */}
        <ShineBorder
          borderWidth={2}
          className="z-20"
          duration={8}
          shineColor={['rgba(255,255,255,0.5)', 'rgba(255,255,255,0.15)', 'transparent']}
        />

        {/* Content */}
        <span className="relative z-10 flex items-center gap-2">{children}</span>
      </button>
    )
  }
)

RichButton.displayName = 'RichButton'

export { RichButton, richButtonVariants }
export default RichButton
