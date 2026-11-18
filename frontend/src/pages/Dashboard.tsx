import { useEffect, useState } from 'react'
import { CalendarCheck, Clock, FileText, Search } from 'lucide-react'
import { Link } from 'react-router-dom'
import StatCard from '../components/StatCard'
import RecommendedJobRow from '../components/RecommendedJobRow'
import { api } from '../lib/api'
import { ApiError } from '../types'
import type { DashboardSummary, JobList } from '../types'

type Status = 'loading' | 'ready' | 'error'

export default function Dashboard() {
  const [status, setStatus] = useState<Status>('loading')
  const [errorText, setErrorText] = useState('')
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [jobs, setJobs] = useState<JobList | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [summaryData, jobsData] = await Promise.all([
          api.get<DashboardSummary>('/dashboard/summary'),
          api.get<JobList>('/jobs', {
            verdict: 'apply',
            dismissed: false,
            has_application: false,
            sort: 'score_desc',
            limit: 5,
          }),
        ])
        if (cancelled) return
        setSummary(summaryData)
        setJobs(jobsData)
        setStatus('ready')
      } catch (error) {
        if (cancelled) return
        setErrorText(
          error instanceof ApiError ? error.detail : 'Could not load the dashboard.',
        )
        setStatus('error')
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [])

  if (status === 'loading') {
    return (
      <div>
        <h1 className="text-2xl font-semibold text-neutral-900">Dashboard</h1>
        <p className="mt-6 text-sm text-neutral-500">Loading...</p>
      </div>
    )
  }

  if (status === 'error' || !summary || !jobs) {
    return (
      <div>
        <h1 className="text-2xl font-semibold text-neutral-900">Dashboard</h1>
        <p className="mt-6 text-sm text-neutral-500">{errorText}</p>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Dashboard</h1>

      <div className="mt-6 grid grid-cols-4 gap-4">
        <StatCard
          label="Total Applications"
          value={summary.total_applications}
          icon={FileText}
        />
        <StatCard label="Interviews" value={summary.interviews} icon={CalendarCheck} />
        <StatCard
          label="Pending Follow-ups"
          value={summary.pending_follow_ups}
          icon={Clock}
        />
        <StatCard label="Jobs Discovered" value={summary.jobs_discovered} icon={Search} />
      </div>

      <div className="mt-6 rounded-lg border border-neutral-200 bg-white p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-baseline gap-2">
            <h2 className="font-semibold text-neutral-900">AI Recommended Jobs</h2>
            <span className="text-sm text-neutral-500">{summary.recommended_jobs} total</span>
          </div>
          <Link
            to="/jobs"
            className="text-sm font-medium text-accent-600 hover:text-accent-700"
          >
            View all
          </Link>
        </div>

        <div className="mt-2 divide-y divide-neutral-200">
          {jobs.items.map((job) => (
            <RecommendedJobRow key={job.id} job={job} />
          ))}
        </div>
      </div>
    </div>
  )
}
