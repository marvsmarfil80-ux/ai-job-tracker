import type { NotificationOut } from '../lib/notifications'

export const sampleNotifications: NotificationOut[] = [
  {
    id: 31,
    type: 'status_changed',
    message: 'Status changed to Under Review: UI Developer',
    link: '/applications/414',
    is_read: false,
    created_at: '2026-11-25T08:00:00Z',
  },
  {
    id: 30,
    type: 'hunt_done',
    message: 'Hunt finished: 3 new jobs (weworkremotely 2, remoteok 1, remotive skipped)',
    link: '/hunts/15',
    is_read: false,
    created_at: '2026-11-25T01:00:00Z',
  },
  {
    id: 29,
    type: 'email_needs_review',
    message: 'Email needs review: no single company match',
    link: '/emails/7',
    is_read: true,
    created_at: '2026-11-24T10:00:00Z',
  },
  {
    id: 28,
    type: 'follow_up_overdue',
    message: 'Follow-up overdue: Send a thank-you note (UI Developer, due Nov 23)',
    link: '/follow-ups/3',
    is_read: true,
    created_at: '2026-11-24T01:00:00Z',
  },
  {
    id: 27,
    type: 'email_sync_failed',
    message: 'Email check failed: Could not reach the n8n webhook.',
    link: null,
    is_read: true,
    created_at: '2026-11-23T09:30:00Z',
  },
]
