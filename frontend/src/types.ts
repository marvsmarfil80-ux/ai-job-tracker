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

export type HuntStep = {
  source: string
  status: 'running' | 'done' | 'error' | 'skipped'
  found: number
  new: number
  message: string | null
}

export type HuntRun = {
  id: number
  trigger: string
  status: 'running' | 'done' | 'error'
  started_at: string
  finished_at: string | null
  total_new: number
  steps: HuntStep[]
}

export type HuntList = {
  items: HuntRun[]
  total: number
  limit: number
  offset: number
}

export type SourceInfo = {
  id: number
  name: string
  badge: string
  enabled: boolean
  keywords: string[]
  max_runs_per_day: number | null
  last_run_at: string | null
  effective_max_runs_per_day: number
  runs_today: number
}

export type ScoreRunResult = {
  requested: number
  attempted: number
  scored: number
  failed: number
  errored: number
  stopped_reason: string | null
  cap: { limit: number; used_before: number; remaining_after: number }
  title_filter: { checked: number; filtered_out: number; passed: number }
}