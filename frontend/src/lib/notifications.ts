export type NotificationType =
  | 'hunt_done'
  | 'follow_up_overdue'
  | 'status_changed'
  | 'email_needs_review'
  | 'email_sync_failed'

export type NotificationTone = 'ok' | 'warn' | 'err' | 'info' | 'idle'

export type NotificationFilter = 'all' | 'unread'

export type NotificationOut = {
  id: number
  type: string
  message: string
  link: string | null
  is_read: boolean
  created_at: string
}

export type NotificationPage = {
  items: NotificationOut[]
  total: number
  unread_count: number
  limit: number
  offset: number
}

export const NOTIFICATION_PAGE_SIZE = 25

const labels: Record<NotificationType, string> = {
  hunt_done: 'Run finished',
  follow_up_overdue: 'Follow-up overdue',
  status_changed: 'Status changed',
  email_needs_review: 'Needs review',
  email_sync_failed: 'Sync failed',
}

const tones: Record<NotificationType, NotificationTone> = {
  hunt_done: 'info',
  follow_up_overdue: 'warn',
  status_changed: 'idle',
  email_needs_review: 'warn',
  email_sync_failed: 'err',
}

export function isKnownType(value: string): value is NotificationType {
  return Object.prototype.hasOwnProperty.call(labels, value)
}

export function labelFor(type: string): string {
  return isKnownType(type) ? labels[type] : 'Notification'
}

export function toneFor(type: string): NotificationTone {
  return isKnownType(type) ? tones[type] : 'idle'
}

const routePrefixes: ReadonlyArray<readonly [string, string]> = [
  ['/hunts/', '/job-hunter'],
  ['/follow-ups/', '/follow-ups'],
  ['/applications/', '/applications'],
  ['/emails/', '/emails'],
]

export function routeForLink(link: string | null): string | null {
  if (!link) return null
  for (const [prefix, route] of routePrefixes) {
    if (link.startsWith(prefix)) return route
  }
  return null
}
