import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check } from 'lucide-react'
import { ApiError } from '../types'
import PageHeader from '../components/PageHeader'
import ErrorState from '../components/ErrorState'
import NotificationList from '../components/NotificationList'
import {
  NOTIFICATION_PAGE_SIZE,
  fetchNotifications,
  markAllNotificationsRead,
  routeForLink,
  setNotificationRead,
  type NotificationFilter,
  type NotificationOut,
} from '../lib/notifications'

const NETWORK_TEXT = 'Could not reach the server. Check that the backend is running, then try again.'

const cardClass = 'rounded-card border border-line bg-surface'

type Loaded = {
  requestKey: string
  viewKey: string
  items: NotificationOut[]
  total: number
  unreadCount: number
}

type LoadError = {
  requestKey: string
  message: string
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return NETWORK_TEXT
    if (error.validation !== null) return error.validation.map((item) => item.msg).join(' ')
    if (typeof error.detail === 'string' && error.detail !== '') return error.detail
  }
  return fallback
}

const filterOptions: { value: NotificationFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'unread', label: 'Unread' },
]

export default function Notifications() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<NotificationFilter>('all')
  const [offset, setOffset] = useState(0)
  const [reloadKey, setReloadKey] = useState(0)
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [loadError, setLoadError] = useState<LoadError | null>(null)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const busyRef = useRef(false)

  const viewKey = filter
  const requestKey = `${filter}|${offset}|${reloadKey}`

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const page = await fetchNotifications(filter, NOTIFICATION_PAGE_SIZE, offset)
        if (cancelled) return
        if (page.items.length === 0 && offset > 0 && page.total > 0) {
          setOffset(Math.floor((page.total - 1) / NOTIFICATION_PAGE_SIZE) * NOTIFICATION_PAGE_SIZE)
          return
        }
        setLoaded({
          requestKey,
          viewKey,
          items: page.items,
          total: page.total,
          unreadCount: page.unread_count,
        })
      } catch (error) {
        if (cancelled) return
        setLoadError({ requestKey, message: errorText(error, 'Could not load notifications.') })
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [filter, offset, requestKey, viewKey])

  const listError = loadError !== null && loadError.requestKey === requestKey ? loadError.message : null
  const unreadCount = loaded?.unreadCount ?? 0
  const total = loaded !== null && loaded.viewKey === viewKey ? loaded.total : 0

  function reload() {
    setReloadKey((value) => value + 1)
  }

  function changeFilter(next: NotificationFilter) {
    setFilter(next)
    setOffset(0)
    setActionError(null)
  }

  function handlePrevious() {
    setOffset((current) => Math.max(0, current - NOTIFICATION_PAGE_SIZE))
    setActionError(null)
  }

  function handleNext() {
    setOffset((current) =>
      current + NOTIFICATION_PAGE_SIZE >= total ? current : current + NOTIFICATION_PAGE_SIZE,
    )
    setActionError(null)
  }

  async function handleToggleRead(id: number, isRead: boolean) {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    setActionError(null)
    try {
      await setNotificationRead(id, isRead)
    } catch (error) {
      setActionError(errorText(error, 'Could not update this notification.'))
    } finally {
      busyRef.current = false
      setBusy(false)
      reload()
    }
  }

  async function handleMarkAll() {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(true)
    setActionError(null)
    try {
      await markAllNotificationsRead()
    } catch (error) {
      setActionError(errorText(error, 'Could not mark all notifications as read.'))
    } finally {
      busyRef.current = false
      setBusy(false)
      reload()
    }
  }

  async function handleOpen(item: NotificationOut) {
    const route = routeForLink(item.link)
    if (route === null || busyRef.current) return
    if (!item.is_read) {
      busyRef.current = true
      setBusy(true)
      await setNotificationRead(item.id, true).catch(() => null)
      busyRef.current = false
      setBusy(false)
    }
    navigate(route)
  }

  function renderList() {
    if (listError !== null) {
      return (
        <section className={cardClass}>
          <ErrorState message={listError} onRetry={reload} />
        </section>
      )
    }
    if (loaded === null || loaded.viewKey !== viewKey) {
      return (
        <section className={`${cardClass} px-6 py-10 text-center text-sm text-ink-muted`}>
          Loading notifications...
        </section>
      )
    }
    return (
      <NotificationList
        items={loaded.items}
        filter={filter}
        offset={offset}
        total={loaded.total}
        disabled={busy}
        onToggleRead={handleToggleRead}
        onOpen={handleOpen}
        onShowAll={() => changeFilter('all')}
        onPrevious={handlePrevious}
        onNext={handleNext}
      />
    )
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
            onClick={handleMarkAll}
            disabled={unreadCount === 0 || busy || loaded === null}
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
              disabled={busy}
              className={`min-h-8 cursor-pointer rounded-md px-3 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed ${
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
      {actionError !== null && (
        <p role="alert" className="mb-4 rounded-lg bg-err-soft px-4 py-3 text-sm text-err-ink">
          {actionError}
        </p>
      )}
      {renderList()}
    </div>
  )
}
