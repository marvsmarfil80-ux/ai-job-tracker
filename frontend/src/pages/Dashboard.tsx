import { useEffect, useState } from 'react'
import { CalendarCheck, Clock, FileText, Search } from 'lucide-react'
import { Link } from 'react-router-dom'
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

  if (status === 'loading') {
    return (
      <div aria-busy="true">
        <h1 className="text-2xl font-semibold text-neutral-900">Dashboard</h1>

        <div className="mt-6 grid grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((index) => (
            <div key={index} className="rounded-lg border border-neutral-200 bg-white p-5">
              <div className="flex items-start justify-between">
                <div>
                  <SkeletonBlock className="h-5 w-28" />
                  <SkeletonBlock className="mt-2 h-9 w-16" />
                </div>
                <SkeletonBlock className="h-10 w-10" />
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 rounded-lg border border-neutral-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-baseline gap-2">
              <h2 className="font-semibold text-neutral-900">AI Recommended Jobs</h2>
              <SkeletonBlock className="h-4 w-14" />
            </div>
            <Link
              to="/jobs"
              className="text-sm font-medium text-accent-600 hover:text-accent-700"
            >
              View all
            </Link>
          </div>

          <div className="mt-2 divide-y divide-neutral-200">
            {[0, 1, 2, 3, 4].map((index) => (
              <div key={index} className="flex items-start justify-between gap-4 py-4">
                <div className="min-w-0 flex-1">
                  <SkeletonBlock className="h-6 w-64" />
                  <SkeletonBlock className="mt-1 h-5 w-48" />
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
        <h1 className="text-2xl font-semibold text-neutral-900">Dashboard</h1>
        <div className="mt-6 rounded-lg border border-neutral-200 bg-white">
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

        {jobs.total === 0 ? (
          <EmptyState
            title="No recommended jobs yet"
            hint="Score new jobs from Job Hunter to see recommendations here."
          />
        ) : (
          <div className="mt-2 divide-y divide-neutral-200">
            {jobs.items.map((job) => (
              <RecommendedJobRow key={job.id} job={job} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
