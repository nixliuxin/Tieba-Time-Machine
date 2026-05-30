import { Moon, Sun } from 'lucide-react'
import { motion } from 'motion/react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useTheme } from '@/contexts/theme-context'
import { cn } from '@/lib/utils'

interface ThemeToggleProps {
  className?: string
  size?: 'icon' | 'icon-xs' | 'icon-sm' | 'icon-lg'
}

export function ThemeToggle({ size = 'icon', className }: ThemeToggleProps) {
  const { theme, setTheme, isDark } = useTheme()

  const toggleTheme = () => {
    if (theme === 'system') {
      const newTheme = isDark ? 'light' : 'dark'
      setTheme(newTheme)
    } else {
      const newTheme = theme === 'light' ? 'dark' : 'light'
      setTheme(newTheme)
    }
  }

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            className={cn('relative', className)}
            onClick={toggleTheme}
            size={size}
            variant="ghost"
          />
        }
      >
        <motion.span
          animate={{
            opacity: isDark ? 1 : 0,
            scale: isDark ? 1 : 0.5,
            rotate: isDark ? 0 : -90,
          }}
          className="absolute"
          initial={false}
          transition={{ duration: 0.2, ease: 'easeOut' }}
        >
          <Sun className="size-4" />
        </motion.span>
        <motion.span
          animate={{
            opacity: isDark ? 0 : 1,
            scale: isDark ? 0.5 : 1,
            rotate: isDark ? 90 : 0,
          }}
          className="absolute"
          initial={false}
          transition={{ duration: 0.2, ease: 'easeOut' }}
        >
          <Moon className="size-4" />
        </motion.span>
      </TooltipTrigger>
      <TooltipContent side="right">{isDark ? 'Light mode' : 'Dark mode'}</TooltipContent>
    </Tooltip>
  )
}
