export type ValidationItem = {
  loc: (string | number)[]
  msg: string
  type: string
}

export class ApiError extends Error {
  status: number
  detail: string
  validation: ValidationItem[] | null

  constructor(status: number, detail: string, validation: ValidationItem[] | null = null) {
    super(detail)
    this.status = status
    this.detail = detail
    this.validation = validation
  }
}

export type DashboardSummary = {
  total_applications: number
  interviews: number
  pending_follow_ups: number
  jobs_discovered: number
  recommended_jobs: number
}

export type JobOut = {
  id: number
  source: string
  title: string
  company: string | null
  url: string
  url_normalized: string
  description: string | null
  location: string | null
  work_mode: string | null
  published: string | null
  priority: number
  pipeline_status: string
  filter_reason: string | null
  opened_at: string | null
  dismissed_at: string | null
  created_at: string
  score: number | null
  verdict: string | null
  reason: string | null
  red_flags: string[] | null
  application_id: number | null
}

export type JobList = {
  items: JobOut[]
  total: number
  limit: number
  offset: number
}

export type ProfileRedactions = {
  emails: number
  phones: number
  lines: number
}

export type ProfileOut = {
  content: string
  updated_at: string
  char_count: number
  groq_view: string
  redactions: ProfileRedactions
  warnings: string[]
}

export type ResumeDraftRedactions = {
  emails: number
  phones: number
  lines: number
  urls: number
  address_lines: number
}

export type ResumeDraftOut = {
  skills: string[]
  draft_content: string
  pages: number
  extracted_chars: number
  truncated: boolean
  redactions: ResumeDraftRedactions
  dropped_skills: number | string[]
  warnings: string[]
}