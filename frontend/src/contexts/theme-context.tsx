import { createContext, useContext, useEffect, useState } from 'react'

type Theme = 'light' | 'dark' | 'system'

interface ThemeContextType {
  isDark: boolean
  isLight: boolean
  isSystem: boolean
  setTheme: (theme: Theme) => void
  theme: Theme
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === 'undefined') return 'dark'
    return (localStorage.getItem('theme') as Theme) || 'dark'
  })

  const [isDark, setIsDark] = useState(() => {
    if (typeof window === 'undefined') return true
    const t = (localStorage.getItem('theme') as Theme) || 'dark'
    return (
      t === 'dark' || (t === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
    )
  })

  useEffect(() => {
    const root = document.documentElement
    const computedIsDark =
      theme === 'dark' ||
      (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)

    setIsDark(computedIsDark)
    root.classList.remove('light', 'dark')
    root.classList.add(computedIsDark ? 'dark' : 'light')
  }, [theme])

  // Listen for system theme changes
  useEffect(() => {
    if (theme !== 'system') return

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = () => {
      const computedIsDark = mediaQuery.matches
      setIsDark(computedIsDark)
      const root = document.documentElement
      root.classList.remove('light', 'dark')
      root.classList.add(computedIsDark ? 'dark' : 'light')
    }

    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [theme])

  const setAndStoreTheme = (newTheme: Theme) => {
    if (newTheme === theme) return
    setTheme(newTheme)
    localStorage.setItem('theme', newTheme)
  }

  return (
    <ThemeContext.Provider
      value={{
        theme,
        setTheme: setAndStoreTheme,
        isDark,
        isLight: !isDark,
        isSystem: theme === 'system',
      }}
    >
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
