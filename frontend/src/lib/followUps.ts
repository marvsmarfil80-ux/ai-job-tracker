export type FollowUpStatus = 'pending' | 'completed'

export type FollowUpFilter = FollowUpStatus

export type FollowUpApplication = {
  application_id: number
  application_status: string
  job_title: string
  job_company: string | null
}

export type FollowUpOut = {
  id: number
  application_id: number
  title: string
  due_date: string | null
  status: FollowUpStatus
  completed_at: string | null
  created_at: string
  is_overdue: boolean
}

export type FollowUpDetail = FollowUpOut & {
  application: FollowUpApplication
}

export type FollowUpList = {
  items: FollowUpDetail[]
  total: number
  limit: number
  offset: number
}

export type FollowUpDraft = {
  application_id: number
  title: string
  due_date: string | null
}

export type FollowUpChanges = {
  title?: string
  due_date?: string | null
  status?: FollowUpStatus
}

export type FollowUpCounts = {
  open: number
  overdue: number
  completed: number
}

export type FollowUpBusy = {
  id: number
  kind: 'toggle' | 'edit' | 'delete'
} | null

export const FOLLOW_UP_PAGE_SIZE = 25

export const TITLE_MAX = 200

const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function formatDueDate(value: string | null): string {
  if (!value) return 'No due date'
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return value
  const month = monthNames[Number(match[2]) - 1]
  if (!month) return value
  return `${month} ${Number(match[3])}, ${match[1]}`
}

export function jobLabel(title: string, company: string | null): string {
  return company ? `${title} · ${company}` : title
}

export function applicationLabel(application: FollowUpApplication): string {
  return jobLabel(application.job_title, application.job_company)
}
