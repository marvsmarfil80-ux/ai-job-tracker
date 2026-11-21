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

export const navItems = [
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
