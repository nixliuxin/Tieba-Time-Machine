/**
 * Motion tokens — reads CSS custom properties once and exports
 * Framer Motion–compatible transition presets.
 *
 * Usage:
 *   import { transitions } from "@/lib/motion-tokens";
 *   <motion.div transition={transitions.fast} />
 *   <motion.div transition={transitions.medium} />
 */

type Ease = [number, number, number, number];

// ---------------------------------------------------------------------------
// Read CSS custom properties once at module load
// ---------------------------------------------------------------------------

const rootStyle = getComputedStyle(document.documentElement);

function readDuration(token: string): number {
  return Number.parseFloat(rootStyle.getPropertyValue(token)) / 1000;
}

const CUBIC_BEZIER_RE =
  /cubic-bezier\(\s*([\d.]+)\s*,\s*([\d.-]+)\s*,\s*([\d.]+)\s*,\s*([\d.-]+)\s*\)/;

function readEase(token: string): Ease {
  const raw = rootStyle.getPropertyValue(token).trim();
  const m = raw.match(CUBIC_BEZIER_RE);
  if (m) {
    return [+(m[1] ?? 0), +(m[2] ?? 0), +(m[3] ?? 0), +(m[4] ?? 0)];
  }
  return [0, 0, 0, 1];
}

// ---------------------------------------------------------------------------
// Durations (seconds)
// ---------------------------------------------------------------------------

export const durations = {
  none: readDuration("--duration-none"),
  micro: readDuration("--duration-83"),
  xmicro: readDuration("--duration-150"),
  short: readDuration("--duration-167"),
  xshort: readDuration("--duration-250"),
  medium: readDuration("--duration-333"),
  xmedium: readDuration("--duration-500"),
  long: readDuration("--duration-667"),
  xlong: readDuration("--duration-1000"),
  xxlong: readDuration("--duration-1500"),
} as const;

// ---------------------------------------------------------------------------
// Easings (cubic-bezier tuples)
// ---------------------------------------------------------------------------

export const easings = {
  linear: readEase("--ease-linear"),
  fast: readEase("--ease-fast"),
  pointToPoint: readEase("--ease-pointtopoint"),
  spring: readEase("--ease-spring"),
  soft: readEase("--ease-soft"),
  inOut: readEase("--ease-inout"),
} as const;

// ---------------------------------------------------------------------------
// Pre-built transition presets for Framer Motion
// ---------------------------------------------------------------------------

export const transitions = {
  /** Panel slide-in/out, quick UI feedback */
  fast: { duration: durations.xshort, ease: easings.fast },
  /** Standard transitions */
  standard: { duration: durations.short, ease: easings.fast },
  /** Point-to-point motion (e.g. indicators) */
  indicator: { duration: durations.xshort, ease: easings.pointToPoint },
  /** Smooth medium-length animations */
  medium: { duration: durations.medium, ease: easings.fast },
  /** Bouncy entrance animations */
  bounce: { duration: durations.short, ease: easings.spring },
} as const;
