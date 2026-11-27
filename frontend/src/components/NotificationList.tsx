import { ArrowUpRight, CircleAlert, Clock, Info, Mail, Radar } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import EmptyState from './EmptyState'
import { formatDateTime } from '../lib/time'
import {
  isKnownType,
  labelFor,
  routeForLink,
  toneFor,
  type NotificationFilter,
  type NotificationOut,
  type NotificationTone,
  type NotificationType,
} from '../lib/notifications'

const icons: Record<NotificationType, LucideIcon> = {
  hunt_done: Radar,
  follow_up_overdue: Clock,
  status_changed: ArrowUpRight,
  email_needs_review: Mail,
  email_sync_failed: CircleAlert,
}

const chipClasses: Record<NotificationTone, string> = {
  ok: 'bg-ok-soft text-ok-ink',
  warn: 'bg-warn-soft text-warn-ink',
  err: 'bg-err-soft text-err-ink',
  info: 'bg-info-soft text-info-ink',
  idle: 'bg-idle-soft text-idle-ink',
}

const secondaryButton =
  'min-h-9 cursor-pointer rounded-lg border border-line bg-surface px-3 text-sm font-medium text-ink transition-colors duration-150 hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50'

type NotificationListProps = {
  items: NotificationOut[]
  filter: NotificationFilter
  offset: number
  total: number
  disabled: boolean
  onToggleRead: (id: number, isRead: boolean) => void
  onOpen: (item: NotificationOut) => void
  onShowAll: () => void
  onPrevious: () => void
  onNext: () => void
}

function RowContent({ item }: { item: NotificationOut }) {
  const Icon = isKnownType(item.type) ? icons[item.type] : Info
  return (
    <>
      <span
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${chipClasses[toneFor(item.type)]}`}
      >
        <Icon size={18} aria-hidden="true" />
      </span>
      <span className="block min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className={`text-sm text-ink ${item.is_read ? 'font-medium' : 'font-semibold'}`}>
            {labelFor(item.type)}
          </span>
          {!item.is_read && (
            <span className="h-2 w-2 shrink-0 rounded-full bg-accent-600">
              <span className="sr-only">Unread</span>
            </span>
          )}
        </span>
        <span className="mt-1 block break-words text-sm text-ink-muted">{item.message}</span>
        <span className="mt-1.5 block text-xs text-ink-muted">{formatDateTime(item.created_at)}</span>
      </span>
    </>
  )
}

export default function NotificationList({
  items,
  filter,
  offset,
  total,
  disabled,
  onToggleRead,
  onOpen,
  onShowAll,
  onPrevious,
  onNext,
}: NotificationListProps) {
  if (total === 0) {
    return (
      <section aria-label="Notifications list" className="rounded-card border border-line bg-surface">
        {filter === 'unread' ? (
          <EmptyState
            title="You're all caught up."
            hint="There are no unread notifications."
            action={
              <button type="button" onClick={onShowAll} disabled={disabled} className={secondaryButton}>
                Show all
              </button>
            }
          />
        ) : (
          <EmptyState
            title="No notifications yet."
            hint="Updates from hunts, follow-ups and application emails appear here."
          />
        )}
      </section>
    )
  }

  const start = offset + 1
  const end = offset + items.length

  return (
    <section
      aria-label="Notifications list"
      className="overflow-hidden rounded-card border border-line bg-surface"
    >
      <ul>
        {items.map((item) => {
          const route = routeForLink(item.link)
          return (
            <li
              key={item.id}
              className={`flex items-center gap-4 border-b border-line px-6 py-4 transition-colors duration-150 last:border-b-0 ${
                route !== null ? 'hover:bg-sunken' : ''
              }`}
            >
              {route !== null ? (
                <button
                  type="button"
                  onClick={() => onOpen(item)}
                  disabled={disabled}
                  className="flex min-w-0 flex-1 cursor-pointer items-start gap-4 rounded-lg text-left disabled:cursor-not-allowed"
                >
                  <RowContent item={item} />
                </button>
              ) : (
                <div className="flex min-w-0 flex-1 items-start gap-4">
                  <RowContent item={item} />
                </div>
              )}
              <div className="flex w-32 shrink-0 justify-end">
                <button
                  type="button"
                  onClick={() => onToggleRead(item.id, !item.is_read)}
                  disabled={disabled}
                  className="min-h-9 cursor-pointer rounded-lg px-2 text-sm font-medium text-accent-ink hover:underline disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {item.is_read ? 'Mark unread' : 'Mark read'}
                </button>
              </div>
            </li>
          )
        })}
      </ul>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-6 py-4">
        <p className="text-sm text-ink-muted">
          Showing {start}-{end} of {total}
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onPrevious}
            disabled={disabled || offset === 0}
            className={secondaryButton}
          >
            Previous
          </button>
          <button
            type="button"
            onClick={onNext}
            disabled={disabled || end >= total}
            className={secondaryButton}
          >
            Next
          </button>
        </div>
      </div>
    </section>
  )
}
