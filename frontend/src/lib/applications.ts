import type { Tone } from './hunt'

export type ApplicationStatus =
  | 'applied'
  | 'under_review'
  | 'assessment'
  | 'interview'
  | 'offer'
  | 'rejected'
  | 'withdrawn'

export type ApplicationJob = {
  id: number
  title: string
  company: string | null
  url: string
  source: string
}

export type ApplicationOut = {
  id: number
  job_id: number
  status: ApplicationStatus
  applied_at: string | null
  notes: string | null
  job: ApplicationJob
}

export type ApplicationEvent = {
  id: number
  from_status: ApplicationStatus | null
  to_status: ApplicationStatus
  changed_at: string
}

export type ApplicationDetail = ApplicationOut & {
  events: ApplicationEvent[]
}

export type ApplicationList = {
  items: ApplicationOut[]
  total: number
  limit: number
  offset: number
}

export type ApplicationChanges = {
  status?: ApplicationStatus
  notes?: string | null
}

export const APPLICATION_PAGE_SIZE = 25

export const NOTES_MAX = 2000

export const HISTORY_TEXT = 'This application has history. Set its status to withdrawn instead.'

export const statusOptions: { value: ApplicationStatus; label: string }[] = [
  { value: 'applied', label: 'Applied' },
  { value: 'under_review', label: 'Under review' },
  { value: 'assessment', label: 'Assessment' },
  { value: 'interview', label: 'Interview' },
  { value: 'offer', label: 'Offer' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'withdrawn', label: 'Withdrawn' },
]

const tones: Record<ApplicationStatus, Tone> = {
  applied: 'idle',
  under_review: 'warn',
  assessment: 'warn',
  interview: 'info',
  offer: 'ok',
  rejected: 'err',
  withdrawn: 'idle',
}

export function applicationStatusLabel(status: string): string {
  return statusOptions.find((option) => option.value === status)?.label ?? status
}

export function applicationStatusTone(status: string): Tone {
  return tones[status as ApplicationStatus] ?? 'idle'
}

export function canDelete(detail: ApplicationDetail): boolean {
  return detail.status === 'applied' && detail.events.length === 1
}
