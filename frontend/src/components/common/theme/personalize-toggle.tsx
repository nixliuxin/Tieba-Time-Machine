import { Dices, Palette, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import {
  BRAND_OPTIONS,
  type BrandId,
  FONT_OPTIONS,
  type FontId,
  RADIUS_OPTIONS,
  type RadiusId,
  SCALE_OPTIONS,
  type ScaleId,
  SURFACE_OPTIONS,
  type SurfaceId,
  usePersonalization,
} from '@/contexts/personalization-context'
import { useTheme } from '@/contexts/theme-context'
import { cn } from '@/lib/utils'

function brandPrimitiveVar(brandId: BrandId): `--color-${BrandId}-500` {
  return `--color-${brandId}-500`
}

function surfacePrimitiveVar(
  surfaceId: SurfaceId,
  mode: 'light' | 'dark'
): `--color-${SurfaceId}-light-6` | `--color-${SurfaceId}-dark-6` {
  return `--color-${surfaceId}-${mode}-6`
}

// Custom — shows actual color, no DS equivalent
function Swatch({
  active,
  cssVar,
  label,
  onClick,
}: {
  active: boolean
  cssVar: string
  label: string
  onClick: () => void
}) {
  return (
    <button
      aria-label={label}
      aria-pressed={active}
      className="group relative size-7 shrink-0 cursor-pointer rounded-full border-2 transition-all hover:scale-110 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
      onClick={onClick}
      style={{
        backgroundColor: `var(${cssVar})`,
        borderColor: active ? 'var(--foreground)' : 'transparent',
      }}
      type="button"
    >
      {active && (
        <span className="absolute inset-0 flex items-center justify-center">
          <span className="size-2 rounded-full bg-foreground" />
        </span>
      )}
    </button>
  )
}

// Custom — the button's own border-radius is the visual preview
function RadiusSwatch({
  active,
  label,
  onClick,
  value,
}: {
  active: boolean
  label: string
  onClick: () => void
  value: string
}) {
  return (
    <button
      aria-label={label}
      aria-pressed={active}
      className={cn(
        'size-7 shrink-0 cursor-pointer border bg-transparent shadow-xs transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50',
        active ? 'border-transparent bg-accent text-accent-foreground' : 'border-input'
      )}
      onClick={onClick}
      style={{ borderRadius: value }}
      type="button"
    />
  )
}

const SCALE_TEXT_CLASS: Record<ScaleId, string> = {
  sm: 'text-xs',
  normal: 'text-sm',
  lg: 'text-base',
  xl: 'text-lg',
}

interface PersonalizeToggleProps {
  className?: string
  popoverClassName?: string
  /** Portal container — use when inside fullscreen elements */
  popoverContainer?: HTMLElement | null
  size?: 'icon' | 'icon-xs' | 'icon-sm' | 'icon-lg'
}

function pickRandom<T>(arr: readonly T[], exclude: T): T {
  const others = arr.filter(v => v !== exclude)
  const index = Math.floor(Math.random() * others.length)
  return others[index] ?? exclude
}

export function PersonalizeToggle({
  size = 'icon',
  className,
  popoverClassName,
  popoverContainer: _popoverContainer,
}: PersonalizeToggleProps) {
  const {
    brand,
    font,
    radius,
    scale,
    surfaceLight,
    surfaceDark,
    dirty,
    reset,
    setBrand,
    setFont,
    setRadius,
    setScale,
    setSurfaceLight,
    setSurfaceDark,
  } = usePersonalization()
  const { isDark } = useTheme()

  const shuffle = () => {
    setBrand(pickRandom(BRAND_OPTIONS, brand))
    setSurfaceLight(pickRandom(SURFACE_OPTIONS, surfaceLight))
    setSurfaceDark(pickRandom(SURFACE_OPTIONS, surfaceDark))
    setRadius(pickRandom(RADIUS_OPTIONS.map(r => r.id) as RadiusId[], radius))
    setScale(pickRandom(SCALE_OPTIONS.map(s => s.id) as ScaleId[], scale))
    setFont(pickRandom(FONT_OPTIONS.map(f => f.id) as FontId[], font))
  }

  return (
    <Popover>
      <PopoverTrigger
        render={
          <Button aria-label="Personalize" className={className} size={size} variant="ghost">
            <Palette className="size-4" />
          </Button>
        }
      />

      <PopoverContent
        align="end"
        className={cn('flex max-h-[min(360px,60vh)] w-60 flex-col p-0', popoverClassName)}
        side="top"
        sideOffset={8}
      >
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="space-y-4 p-3">
            {/* Brand color */}
            <div className="space-y-1.5">
              <span className="font-medium text-muted-foreground text-xs">Primary</span>
              <div className="flex flex-wrap gap-2">
                {BRAND_OPTIONS.map(id => (
                  <Swatch
                    active={brand === id}
                    cssVar={brandPrimitiveVar(id)}
                    key={id}
                    label={id}
                    onClick={() => setBrand(id as BrandId)}
                  />
                ))}
              </div>
            </div>

            {/* Surface */}
            <div className="space-y-1.5">
              <span className="font-medium text-muted-foreground text-xs">
                Surface {isDark ? '(dark)' : '(light)'}
              </span>
              <div className="flex flex-wrap gap-2">
                {SURFACE_OPTIONS.map(id => (
                  <Swatch
                    active={isDark ? surfaceDark === id : surfaceLight === id}
                    cssVar={surfacePrimitiveVar(id, isDark ? 'dark' : 'light')}
                    key={id}
                    label={id}
                    onClick={() => (isDark ? setSurfaceDark : setSurfaceLight)(id as SurfaceId)}
                  />
                ))}
              </div>
            </div>

            {/* Radius */}
            <div className="space-y-1.5">
              <span className="font-medium text-muted-foreground text-xs">Radius</span>
              <div className="flex gap-1.5">
                {RADIUS_OPTIONS.map(opt => (
                  <RadiusSwatch
                    active={radius === opt.id}
                    key={opt.id}
                    label={opt.label}
                    onClick={() => setRadius(opt.id)}
                    value={opt.value}
                  />
                ))}
              </div>
            </div>

            {/* Type size */}
            <div className="space-y-1.5">
              <span className="font-medium text-muted-foreground text-xs">Type size</span>
              <ToggleGroup
                onValueChange={v => v.length > 0 && setScale(v[0] as ScaleId)}
                spacing={0}
                value={[scale]}
                variant="outline"
              >
                {SCALE_OPTIONS.map(opt => (
                  <ToggleGroupItem
                    aria-label={opt.label}
                    className={cn('size-7 px-0', SCALE_TEXT_CLASS[opt.id])}
                    key={opt.id}
                    value={opt.id}
                  >
                    Aa
                  </ToggleGroupItem>
                ))}
              </ToggleGroup>
            </div>

            {/* Font */}
            <div className="space-y-1.5">
              <span className="font-medium text-muted-foreground text-xs">Font</span>
              <div className="flex flex-col gap-0.5">
                {FONT_OPTIONS.map(opt => (
                  <button
                    aria-pressed={font === opt.id}
                    className={cn(
                      'cursor-pointer rounded-md px-2 py-1 text-left text-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50',
                      font === opt.id ? 'bg-accent font-medium text-accent-foreground' : ''
                    )}
                    key={opt.id}
                    onClick={() => setFont(opt.id)}
                    style={{ fontFamily: opt.family }}
                    type="button"
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="flex gap-2 border-t p-3 pt-2.5">
          {dirty && (
            <Button className="flex-1" onClick={reset} size="sm" variant="ghost">
              <RotateCcw className="size-3.5" />
              Reset
            </Button>
          )}
          <Button className="flex-1" onClick={shuffle} size="sm" variant="outline">
            <Dices className="size-3.5" />
            Shuffle
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
