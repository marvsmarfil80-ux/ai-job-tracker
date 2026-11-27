import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import NotificationList from '../components/NotificationList'
import { sampleNotifications } from '../data/notificationsSample'
import {
  NOTIFICATION_PAGE_SIZE,
  routeForLink,
  type NotificationFilter,
  type NotificationOut,
} from '../lib/notifications'

const filterOptions: { value: NotificationFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'unread', label: 'Unread' },
]

export default function Notifications() {
  const navigate = useNavigate()
  const [items, setItems] = useState<NotificationOut[]>(sampleNotifications)
  const [filter, setFilter] = useState<NotificationFilter>('all')
  const [offset, setOffset] = useState(0)

  const unreadCount = items.filter((item) => !item.is_read).length
  const visible = filter === 'unread' ? items.filter((item) => !item.is_read) : items
  const total = visible.length
  const pageItems = visible.slice(offset, offset + NOTIFICATION_PAGE_SIZE)

  function setRead(id: number, isRead: boolean) {
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, is_read: isRead } : item)),
    )
  }

  function markAllRead() {
    setItems((current) => current.map((item) => ({ ...item, is_read: true })))
  }

  function changeFilter(next: NotificationFilter) {
    setFilter(next)
    setOffset(0)
  }

  function openItem(item: NotificationOut) {
    const route = routeForLink(item.link)
    if (route === null) return
    if (!item.is_read) setRead(item.id, true)
    navigate(route)
  }

  return (
    <div>
      <PageHeader
        eyebrow="IN-APP ONLY"
        title="Notifications"
        description="Updates from hunts, follow-ups and application emails."
        actions={
          <button
            type="button"
            onClick={markAllRead}
            disabled={unreadCount === 0}
            className="inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-lg bg-accent-600 px-4 text-sm font-medium text-white transition-colors duration-150 hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Check size={16} aria-hidden="true" />
            Mark all read
          </button>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-medium text-accent-soft-ink">
          <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />
          {unreadCount} unread
        </span>
        <div
          role="group"
          aria-label="Show notifications"
          className="inline-flex items-center gap-1 rounded-lg bg-sunken p-1"
        >
          {filterOptions.map((option) => (
            <button
              key={option.value}
              type="button"
              aria-pressed={filter === option.value}
              onClick={() => changeFilter(option.value)}
              className={`min-h-8 cursor-pointer rounded-md px-3 text-sm font-medium transition-colors duration-150 ${
                filter === option.value
                  ? 'bg-surface text-ink shadow-sm'
                  : 'text-ink-muted hover:text-ink'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
      <NotificationList
        items={pageItems}
        filter={filter}
        offset={offset}
        total={total}
        onToggleRead={setRead}
        onOpen={openItem}
        onShowAll={() => changeFilter('all')}
        onPrevious={() => setOffset((value) => Math.max(0, value - NOTIFICATION_PAGE_SIZE))}
        onNext={() => setOffset((value) => value + NOTIFICATION_PAGE_SIZE)}
      />
    </div>
  )
}
