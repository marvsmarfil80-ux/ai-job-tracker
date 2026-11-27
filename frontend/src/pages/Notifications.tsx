import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check } from 'lucide-react'
import { ApiError } from '../types'
import PageHeader from '../components/PageHeader'
import ErrorState from '../components/ErrorState'
import NotificationList, { NotificationListSkeleton } from '../components/NotificationList'
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

const GONE_TEXT = 'This notification no longer exists. The list was refreshed.'

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

type Busy = number | 'all' | null

type Notice = {
  message: string
  tone: 'err' | 'warn'
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return NETWORK_TEXT
    if (error.status === 502 && error.detail === 'Request failed (502)') return NETWORK_TEXT
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
  const [busy, setBusy] = useState<Busy>(null)
  const [notice, setNotice] = useState<Notice | null>(null)
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
  const busyActive = busy !== null
  const listStatus: 'skeleton' | 'refreshing' | 'ready' =
    loaded !== null && loaded.requestKey === requestKey
      ? 'ready'
      : loaded !== null && loaded.viewKey === viewKey
        ? 'refreshing'
        : 'skeleton'
  const loadingText = listError === null && listStatus !== 'ready' ? 'Loading notifications.' : ''

  function reload() {
    setReloadKey((value) => value + 1)
  }

  function changeFilter(next: NotificationFilter) {
    setFilter(next)
    setOffset(0)
    setNotice(null)
  }

  function handlePrevious() {
    setOffset((current) => Math.max(0, current - NOTIFICATION_PAGE_SIZE))
    setNotice(null)
  }

  function handleNext() {
    setOffset((current) =>
      current + NOTIFICATION_PAGE_SIZE >= total ? current : current + NOTIFICATION_PAGE_SIZE,
    )
    setNotice(null)
  }

  async function handleToggleRead(id: number, isRead: boolean) {
    if (busyRef.current) return
    busyRef.current = true
    setBusy(id)
    setNotice(null)
    try {
      await setNotificationRead(id, isRead)
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setNotice({ message: GONE_TEXT, tone: 'warn' })
      } else {
        setNotice({ message: errorText(error, 'Could not update this notification.'), tone: 'err' })
      }
    } finally {
      busyRef.current = false
      setBusy(null)
      reload()
    }
  }

  async function handleMarkAll() {
    if (busyRef.current) return
    busyRef.current = true
    setBusy('all')
    setNotice(null)
    try {
      await markAllNotificationsRead()
    } catch (error) {
      setNotice({
        message: errorText(error, 'Could not mark all notifications as read.'),
        tone: 'err',
      })
    } finally {
      busyRef.current = false
      setBusy(null)
      reload()
    }
  }

  async function handleOpen(item: NotificationOut) {
    const route = routeForLink(item.link)
    if (route === null || busyRef.current) return
    if (!item.is_read) {
      busyRef.current = true
      setBusy(item.id)
      await setNotificationRead(item.id, true).catch(() => null)
      busyRef.current = false
      setBusy(null)
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
    if (loaded === null || listStatus === 'skeleton') {
      return <NotificationListSkeleton />
    }
    return (
      <NotificationList
        items={loaded.items}
        filter={filter}
        offset={offset}
        total={loaded.total}
        disabled={busyActive || listStatus !== 'ready'}
        refreshing={listStatus === 'refreshing'}
        busyId={typeof busy === 'number' ? busy : null}
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
            disabled={unreadCount === 0 || busyActive || loaded === null}
            className="inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-lg bg-accent-600 px-4 text-sm font-medium text-white transition-colors duration-150 hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === 'all' ? (
              'Marking...'
            ) : (
              <>
                <Check size={16} aria-hidden="true" />
                Mark all read
              </>
            )}
          </button>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        {loaded !== null && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-medium text-accent-soft-ink">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />
            {unreadCount} unread
          </span>
        )}
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
              disabled={busyActive}
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
      <p role="status" className="sr-only">
        {loadingText}
      </p>
      {notice !== null && (
        <p
          role={notice.tone === 'err' ? 'alert' : 'status'}
          className={`mb-4 rounded-lg px-4 py-3 text-sm ${
            notice.tone === 'err' ? 'bg-err-soft text-err-ink' : 'bg-warn-soft text-warn-ink'
          }`}
        >
          {notice.message}
        </p>
      )}
      {renderList()}
    </div>
  )
}
