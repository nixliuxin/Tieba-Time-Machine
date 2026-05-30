import { useCallback, useState } from 'react'
import { useIntersectionObserver } from './use-intersection-observer'

interface UseLazyMediaOptions {
  enabled?: boolean
  rootMargin?: string
  threshold?: number
}

export function useLazyMedia(options: UseLazyMediaOptions = {}) {
  const {
    rootMargin = '100px', // Start loading 100px before entering viewport
    threshold = 0.1,
    enabled = true,
  } = options

  const [hasLoaded, setHasLoaded] = useState(!enabled) // If not enabled, consider it loaded
  const [elementRef, isIntersecting] = useIntersectionObserver<HTMLDivElement>({
    rootMargin,
    threshold,
    freezeOnceVisible: true, // Once visible, stay loaded
  })

  // Mark as loaded when intersecting for the first time
  const shouldLoad = isIntersecting || hasLoaded

  const markAsLoaded = useCallback(() => {
    setHasLoaded(true)
  }, [])

  return {
    ref: elementRef,
    shouldLoad,
    isIntersecting,
    hasLoaded,
    markAsLoaded,
  }
}
