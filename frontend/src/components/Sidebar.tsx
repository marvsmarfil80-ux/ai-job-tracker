import { NavLink } from 'react-router-dom'
import { Radar } from 'lucide-react'
import { navItems } from '../lib/nav'
import ThemeToggle from './ThemeToggle'

export default function Sidebar() {
  return (
    <aside className="flex w-[242px] shrink-0 flex-col overflow-y-auto border-r border-line bg-surface px-3.5 pb-4 pt-6">
      <div className="flex items-center gap-3 px-3 pb-6">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-soft text-accent-soft-ink">
          <Radar size={18} aria-hidden="true" />
        </span>
        <span className="text-base font-semibold text-ink">AI Job Tracker</span>
      </div>
      <nav aria-label="Main" className="flex flex-col gap-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex min-h-9 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors duration-150 ${
                isActive
                  ? 'bg-accent-soft text-accent-soft-ink'
                  : 'text-ink-muted hover:bg-sunken hover:text-ink'
              }`
            }
          >
            <Icon size={18} aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto pt-4">
        <ThemeToggle />
      </div>
    </aside>
  )
}
