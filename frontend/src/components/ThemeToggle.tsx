import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'

function readStored(): 'light' | 'dark' | null {
  try {
    const value = localStorage.getItem('theme')
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null
  }
}

function writeStored(value: 'light' | 'dark'): boolean {
  try {
    localStorage.setItem('theme', value)
    return true
  } catch {
    return false
  }
}

function applyTheme(dark: boolean) {
  document.documentElement.classList.toggle('dark', dark)
}

export default function ThemeToggle() {
  const [dark, setDark] = useState(() =>
    document.documentElement.classList.contains('dark'),
  )

  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (event: MediaQueryListEvent) => {
      if (readStored() === null) {
        applyTheme(event.matches)
        setDark(event.matches)
      }
    }
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  function toggle() {
    const next = !dark
    applyTheme(next)
    setDark(next)
    writeStored(next ? 'dark' : 'light')
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={dark}
      className="flex min-h-9 w-full items-center gap-3 rounded-lg px-3 text-sm font-medium text-ink-muted transition-colors duration-150 hover:bg-sunken hover:text-ink"
    >
      {dark ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
      Dark mode
    </button>
  )
}
