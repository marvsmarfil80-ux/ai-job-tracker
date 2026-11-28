import { NavLink } from 'react-router-dom'
import { Radar } from 'lucide-react'
import { navItems } from '../lib/nav'
import ThemeToggle from './ThemeToggle'

type SidebarProps = {
  onNavigate?: () => void
}

export default function Sidebar({ onNavigate }: SidebarProps) {
  return (
    <aside className="flex w-[242px] shrink-0 flex-col overflow-y-auto overscroll-contain border-r border-line bg-chrome px-3.5 pb-4 pt-6">
      <div className="flex items-center gap-3 px-3 pb-6">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-accent-600 text-white shadow-card">
          <Radar size={18} aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <p className="text-base font-semibold leading-tight text-ink">AI Job Tracker</p>
          <p className="text-xs text-ink-subtle">Personal workspace</p>
        </div>
      </div>
      <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-widest text-ink-subtle">
        Workspace
      </p>
      <nav aria-label="Main" className="flex flex-col gap-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
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
      <div className="mt-auto flex flex-col gap-3 pt-4">
        <div className="rounded-xl border border-line bg-sunken p-3">
          <p className="text-xs font-semibold text-ink">Local workspace</p>
          <p className="mt-1 text-xs text-ink-muted">Asia/Manila · read-only Gmail</p>
        </div>
        <ThemeToggle />
      </div>
    </aside>
  )
}
