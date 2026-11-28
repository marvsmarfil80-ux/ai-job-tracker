import { useEffect, useState } from 'react'
import { CalendarCheck, Clock, FileText, Search } from 'lucide-react'
import { Link } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import StatCard from '../components/StatCard'
import RecommendedJobRow from '../components/RecommendedJobRow'
import SkeletonBlock from '../components/SkeletonBlock'
import EmptyState from '../components/EmptyState'
import ErrorState from '../components/ErrorState'
import { api } from '../lib/api'
import { ApiError } from '../types'
import type { DashboardSummary, JobList } from '../types'

type Status = 'loading' | 'ready' | 'error'

export default function Dashboard() {
  const [status, setStatus] = useState<Status>('loading')
  const [errorText, setErrorText] = useState('')
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [jobs, setJobs] = useState<JobList | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

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
          error instanceof ApiError && typeof error.detail === 'string'
            ? error.detail
            : 'Could not load the dashboard.',
        )
        setStatus('error')
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [reloadKey])

  function handleRetry() {
    setStatus('loading')
    setReloadKey((key) => key + 1)
  }

  const header = (
    <PageHeader
      eyebrow="Overview"
      title="Dashboard"
      description="A summary of your applications, follow-ups and discovered jobs."
    />
  )

  if (status === 'loading') {
    return (
      <div aria-busy="true">
        {header}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 min-[1050px]:grid-cols-4">
          {[0, 1, 2, 3].map((index) => (
            <div
              key={index}
              className="flex items-center gap-4 rounded-card border border-line bg-surface p-5 shadow-card"
            >
              <SkeletonBlock className="h-10 w-10 shrink-0" />
              <div>
                <SkeletonBlock className="h-5 w-28" />
                <SkeletonBlock className="mt-2 h-9 w-16" />
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 rounded-card border border-line bg-surface p-5 shadow-card">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-widest text-ink-subtle">
                AI signal
              </p>
              <div className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-1">
                <h2 className="text-base font-semibold text-ink">AI Recommended Jobs</h2>
                <SkeletonBlock className="h-4 w-14" />
              </div>
              <p className="mt-1 text-sm text-ink-muted">Top matches waiting for your decision.</p>
            </div>
            <Link
              to="/jobs"
              className="shrink-0 text-sm font-medium text-accent-ink underline-offset-4 hover:underline"
            >
              View all
            </Link>
          </div>

          <div className="mt-2 divide-y divide-line">
            {[0, 1, 2, 3, 4].map((index) => (
              <div key={index} className="flex items-start gap-4 py-4">
                <SkeletonBlock className="h-7 w-7 shrink-0" />
                <div className="min-w-0 flex-1">
                  <SkeletonBlock className="h-6 w-full max-w-64" />
                  <SkeletonBlock className="mt-1 h-5 w-full max-w-48" />
                  <SkeletonBlock className="mt-2 h-10 w-full" />
                </div>
                <SkeletonBlock className="h-7 w-10" />
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (status === 'error' || !summary || !jobs) {
    return (
      <div>
        {header}
        <div className="rounded-card border border-line bg-surface shadow-card">
          <ErrorState
            message={errorText || 'Could not load the dashboard.'}
            onRetry={handleRetry}
          />
        </div>
      </div>
    )
  }

  return (
    <div>
      {header}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 min-[1050px]:grid-cols-4">
        <StatCard
          label="Total Applications"
          value={summary.total_applications}
          icon={FileText}
        />
        <StatCard
          label="Pending Follow-ups"
          value={summary.pending_follow_ups}
          icon={Clock}
          tone="warn"
        />
        <StatCard
          label="Interviews"
          value={summary.interviews}
          icon={CalendarCheck}
          tone="info"
        />
        <StatCard
          label="Jobs Discovered"
          value={summary.jobs_discovered}
          icon={Search}
          tone="ok"
        />
      </div>

      <div className="mt-6 rounded-card border border-line bg-surface p-5 shadow-card">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-widest text-ink-subtle">
              AI signal
            </p>
            <div className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <h2 className="text-base font-semibold text-ink">AI Recommended Jobs</h2>
              <span className="text-sm text-ink-muted">{summary.recommended_jobs} total</span>
            </div>
            <p className="mt-1 text-sm text-ink-muted">Top matches waiting for your decision.</p>
          </div>
          <Link
            to="/jobs"
            className="shrink-0 text-sm font-medium text-accent-ink underline-offset-4 hover:underline"
          >
            View all
          </Link>
        </div>

        {jobs.total === 0 ? (
          <EmptyState
            title="No recommended jobs yet"
            hint="Score new jobs from Job Hunter to see recommendations here."
          />
        ) : (
          <div className="mt-2 divide-y divide-line">
            {jobs.items.map((job, index) => (
              <RecommendedJobRow key={job.id} job={job} rank={index + 1} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
