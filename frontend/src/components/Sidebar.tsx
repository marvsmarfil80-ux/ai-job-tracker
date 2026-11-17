import { NavLink } from 'react-router-dom'
import {
  Bell,
  Briefcase,
  ClipboardList,
  Clock,
  LayoutDashboard,
  Mail,
  Search,
  Settings,
  User,
} from 'lucide-react'

const items = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/job-hunter', label: 'Job Hunter', icon: Search },
  { to: '/jobs', label: 'Jobs to Apply', icon: Briefcase },
  { to: '/applications', label: 'Applications', icon: ClipboardList },
  { to: '/notifications', label: 'Notifications', icon: Bell },
  { to: '/follow-ups', label: 'Follow-ups', icon: Clock },
  { to: '/emails', label: 'Application Emails', icon: Mail },
  { to: '/profile', label: 'My Profile', icon: User },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function Sidebar() {
  return (
    <nav className="flex w-64 shrink-0 flex-col gap-1 border-r border-neutral-200 bg-white p-4">
      <div className="mb-4 px-3 text-lg font-semibold text-neutral-900">
        AI Job Tracker
      </div>
      {items.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium ${
              isActive
                ? 'bg-accent-50 text-accent-700'
                : 'text-neutral-600 hover:bg-neutral-100'
            }`
          }
        >
          <Icon size={18} />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}