import { createContext, useContext, useEffect, useState } from 'react'

// Available palette options — matches website/src/styles/tokens/primitives.css (b1–b6, n1–n6)
export const BRAND_OPTIONS = ['b1', 'b2', 'b3', 'b4', 'b5', 'b6'] as const
export const SURFACE_OPTIONS = ['n1', 'n2', 'n3', 'n4', 'n5', 'n6'] as const
export const RADIUS_OPTIONS = [
  { id: 'none', label: 'Sharp', value: 'var(--corner-radius-none)' },
  { id: 'sm', label: 'Subtle', value: 'var(--corner-radius-sm)' },
  { id: 'md', label: 'Default', value: 'var(--corner-radius-md)' },
  { id: 'lg', label: 'Round', value: 'var(--corner-radius-lg)' },
] as const
// Values match --typography-scale in typography-fluid.css
export const SCALE_OPTIONS = [
  { id: 'sm', label: 'S', value: 0.9 },
  { id: 'normal', label: 'M', value: 1 },
  { id: 'lg', label: 'L', value: 1.1 },
  { id: 'xl', label: 'XL', value: 1.2 },
] as const
export const FONT_OPTIONS = [
  { id: 'inter', label: 'Inter', family: '"Inter", ui-sans-serif, system-ui, sans-serif' },
  { id: 'geist', label: 'Geist', family: '"Geist", ui-sans-serif, system-ui, sans-serif' },
  {
    id: 'instrument',
    label: 'Instrument Sans',
    family: '"Instrument Sans", ui-sans-serif, system-ui, sans-serif',
  },
  {
    id: 'space',
    label: 'Space Grotesk',
    family: '"Space Grotesk", ui-sans-serif, system-ui, sans-serif',
  },
  { id: 'nunito', label: 'Nunito', family: '"Nunito", ui-sans-serif, system-ui, sans-serif' },
] as const

export type BrandId = (typeof BRAND_OPTIONS)[number]
export type SurfaceId = (typeof SURFACE_OPTIONS)[number]
export type RadiusId = (typeof RADIUS_OPTIONS)[number]['id']
export type ScaleId = (typeof SCALE_OPTIONS)[number]['id']
export type FontId = (typeof FONT_OPTIONS)[number]['id']

interface PersonalizationState {
  brand: BrandId | null
  font: FontId | null
  radius: RadiusId | null
  scale: ScaleId | null
  surfaceDark: SurfaceId | null
  surfaceLight: SurfaceId | null
}

interface PersonalizationContextType {
  brand: BrandId
  dirty: boolean
  font: FontId
  radius: RadiusId
  reset: () => void
  scale: ScaleId
  setBrand: (brand: BrandId) => void
  setFont: (font: FontId) => void
  setRadius: (radius: RadiusId) => void
  setScale: (scale: ScaleId) => void
  setSurfaceDark: (surface: SurfaceId) => void
  setSurfaceLight: (surface: SurfaceId) => void
  surfaceDark: SurfaceId
  surfaceLight: SurfaceId
}

const STORAGE_KEY = 'personalization'

const CSS_DEFAULTS = {
  brand: 'b1' as BrandId,
  surfaceLight: 'n1' as SurfaceId,
  surfaceDark: 'n1' as SurfaceId,
  radius: 'md' as RadiusId,
  scale: 'normal' as ScaleId,
  font: 'inter' as FontId,
}

const RADIUS_IDS = RADIUS_OPTIONS.map(r => r.id) as readonly string[]
const SCALE_IDS = SCALE_OPTIONS.map(s => s.id) as readonly string[]
const FONT_IDS = FONT_OPTIONS.map(f => f.id) as readonly string[]

function loadState(): PersonalizationState {
  if (typeof window === 'undefined')
    return {
      brand: null,
      surfaceLight: null,
      surfaceDark: null,
      radius: null,
      scale: null,
      font: null,
    }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw)
      return {
        brand: null,
        surfaceLight: null,
        surfaceDark: null,
        radius: null,
        scale: null,
        font: null,
      }
    const parsed = JSON.parse(raw)
    return {
      brand: BRAND_OPTIONS.includes(parsed.brand) ? parsed.brand : null,
      surfaceLight: SURFACE_OPTIONS.includes(parsed.surfaceLight) ? parsed.surfaceLight : null,
      surfaceDark: SURFACE_OPTIONS.includes(parsed.surfaceDark) ? parsed.surfaceDark : null,
      radius: RADIUS_IDS.includes(parsed.radius) ? parsed.radius : null,
      scale: SCALE_IDS.includes(parsed.scale) ? parsed.scale : null,
      font: FONT_IDS.includes(parsed.font) ? parsed.font : null,
    }
  } catch {
    return {
      brand: null,
      surfaceLight: null,
      surfaceDark: null,
      radius: null,
      scale: null,
      font: null,
    }
  }
}

function applyToDOM(state: PersonalizationState) {
  const root = document.documentElement

  if (state.brand) {
    root.style.setProperty('--primary', `var(--color-${state.brand}-500)`)
  } else {
    root.style.removeProperty('--primary')
  }

  for (let i = 1; i <= 12; i++) {
    if (state.surfaceLight) {
      root.style.setProperty(
        `--surface-light-${i}`,
        `var(--color-${state.surfaceLight}-light-${i})`
      )
    } else {
      root.style.removeProperty(`--surface-light-${i}`)
    }
    if (state.surfaceDark) {
      root.style.setProperty(`--surface-dark-${i}`, `var(--color-${state.surfaceDark}-dark-${i})`)
    } else {
      root.style.removeProperty(`--surface-dark-${i}`)
    }
  }

  if (state.radius) {
    root.style.setProperty('--corner-radius', `var(--corner-radius-${state.radius})`)
  } else {
    root.style.removeProperty('--corner-radius')
  }

  if (state.scale) {
    const opt = SCALE_OPTIONS.find(s => s.id === state.scale)
    if (opt) root.style.setProperty('--typography-scale', String(opt.value))
  } else {
    root.style.removeProperty('--typography-scale')
  }

  if (state.font) {
    const opt = FONT_OPTIONS.find(f => f.id === state.font)
    if (opt) root.style.setProperty('--font-family-sans', opt.family)
  } else {
    root.style.removeProperty('--font-family-sans')
  }
}

const PersonalizationContext = createContext<PersonalizationContextType | undefined>(undefined)

export function PersonalizationProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<PersonalizationState>(loadState)

  useEffect(() => {
    applyToDOM(state)
    if (
      state.brand ||
      state.surfaceLight ||
      state.surfaceDark ||
      state.radius ||
      state.scale ||
      state.font
    ) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  }, [state])

  const dirty = !!(
    state.brand ||
    state.surfaceLight ||
    state.surfaceDark ||
    state.radius ||
    state.scale ||
    state.font
  )

  const setBrand = (brand: BrandId) => setState(s => ({ ...s, brand }))
  const setSurfaceLight = (surfaceLight: SurfaceId) => setState(s => ({ ...s, surfaceLight }))
  const setSurfaceDark = (surfaceDark: SurfaceId) => setState(s => ({ ...s, surfaceDark }))
  const setRadius = (radius: RadiusId) =>
    setState(s => ({ ...s, radius: radius === CSS_DEFAULTS.radius ? null : radius }))
  const setScale = (scale: ScaleId) =>
    setState(s => ({ ...s, scale: scale === CSS_DEFAULTS.scale ? null : scale }))
  const setFont = (font: FontId) =>
    setState(s => ({ ...s, font: font === CSS_DEFAULTS.font ? null : font }))
  const reset = () =>
    setState({
      brand: null,
      surfaceLight: null,
      surfaceDark: null,
      radius: null,
      scale: null,
      font: null,
    })

  return (
    <PersonalizationContext.Provider
      value={{
        brand: state.brand ?? CSS_DEFAULTS.brand,
        surfaceLight: state.surfaceLight ?? CSS_DEFAULTS.surfaceLight,
        surfaceDark: state.surfaceDark ?? CSS_DEFAULTS.surfaceDark,
        radius: state.radius ?? CSS_DEFAULTS.radius,
        scale: state.scale ?? CSS_DEFAULTS.scale,
        font: state.font ?? CSS_DEFAULTS.font,
        dirty,
        reset,
        setBrand,
        setSurfaceLight,
        setSurfaceDark,
        setRadius,
        setScale,
        setFont,
      }}
    >
      {children}
    </PersonalizationContext.Provider>
  )
}

export function usePersonalization() {
  const context = useContext(PersonalizationContext)
  if (!context) throw new Error('usePersonalization must be used within PersonalizationProvider')
  return context
}
