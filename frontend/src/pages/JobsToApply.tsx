import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { ApiError } from '../types'
import type { JobList, JobOut } from '../types'
import PageHeader from '../components/PageHeader'
import ErrorState from '../components/ErrorState'
import JobsFilterBar from '../components/JobsFilterBar'
import type { JobFilters } from '../components/JobsFilterBar'
import JobsTable from '../components/JobsTable'
import type { JobsTab } from '../components/JobsTable'
import { PAGE_SIZE } from '../lib/jobs'

const initialFilters: JobFilters = {
  search: '',
  verdict: '',
  pipeline: '',
  sort: '',
  openedOnly: false,
}

const DISMISSED_DETAIL = 'This job is dismissed. Restore it first.'

function errorText(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.validation !== null) return error.validation.map((item) => item.msg).join(' ')
    if (typeof error.detail === 'string' && error.detail !== '') return error.detail
  }
  return fallback
}

function buildQuery(
  dismissed: boolean,
  verdict: string,
  pipeline: string,
  sort: string,
  openedOnly: boolean,
  search: string,
  limit: number,
  offset: number,
): string {
  const params = new URLSearchParams()
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  params.set('dismissed', String(dismissed))
  if (search !== '') params.set('q', search)
  if (verdict !== '') params.set('verdict', verdict)
  if (pipeline !== '') params.set('pipeline_status', pipeline)
  if (sort !== '') params.set('sort', sort)
  if (openedOnly) params.set('awaiting_apply', 'true')
  return `/jobs?${params.toString()}`
}

export default function JobsToApply() {
  const [tab, setTab] = useState<JobsTab>('active')
  const [filters, setFilters] = useState<JobFilters>(initialFilters)
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [jobs, setJobs] = useState<JobOut[] | null>(null)
  const [total, setTotal] = useState(0)
  const [otherTotal, setOtherTotal] = useState(0)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({})

  const { verdict, pipeline, sort, openedOnly } = filters

  useEffect(() => {
    const trimmed = filters.search.trim()
    const timer = window.setTimeout(() => {
      setSearch(trimmed)
      setOffset(0)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [filters.search])

  useEffect(() => {
    let cancelled = false
    const isDismissedTab = tab === 'dismissed'

    async function load() {
      try {
        const [list, other] = await Promise.all([
          api.get<JobList>(
            buildQuery(isDismissedTab, verdict, pipeline, sort, openedOnly, search, PAGE_SIZE, offset),
          ),
          api.get<JobList>(
            buildQuery(!isDismissedTab, verdict, pipeline, sort, openedOnly, search, 1, 0),
          ),
        ])
        if (cancelled) return
        if (list.items.length === 0 && offset > 0 && list.total > 0) {
          setOffset(Math.floor((list.total - 1) / PAGE_SIZE) * PAGE_SIZE)
          return
        }
        setJobs(list.items)
        setTotal(list.total)
        setOtherTotal(other.total)
        setLoadError(null)
      } catch (error) {
        if (cancelled) return
        setLoadError(errorText(error, 'Could not load jobs.'))
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [tab, verdict, pipeline, sort, openedOnly, search, offset, reloadKey])

  function handleRetry() {
    setLoadError(null)
    setReloadKey((key) => key + 1)
  }

  function handleFiltersChange(next: JobFilters) {
    const changed =
      next.verdict !== filters.verdict ||
      next.pipeline !== filters.pipeline ||
      next.sort !== filters.sort ||
      next.openedOnly !== filters.openedOnly
    setFilters(next)
    if (changed) {
      setOffset(0)
      setExpandedId(null)
    }
  }

  function handleClear() {
    setFilters(initialFilters)
    setSearch('')
    setOffset(0)
    setExpandedId(null)
  }

  function handleTabChange(next: JobsTab) {
    setTab(next)
    setOffset(0)
    setExpandedId(null)
  }

  function handleToggle(id: number) {
    setExpandedId((current) => (current === id ? null : id))
  }

  function setRowError(id: number, message: string | null) {
    setRowErrors((current) => {
      const next = { ...current }
      if (message === null) delete next[id]
      else next[id] = message
      return next
    })
  }

  async function handleOpen(id: number) {
    setRowError(id, null)
    try {
      const updated = await api.post<JobOut>(`/jobs/${id}/open`)
      setJobs((current) =>
        current === null ? current : current.map((job) => (job.id === id ? updated : job)),
      )
    } catch (error) {
      setRowError(id, errorText(error, 'Could not record that the listing was opened.'))
    }
  }

  async function handleDismiss(id: number) {
    if (busyId !== null) return
    setBusyId(id)
    setRowError(id, null)
    try {
      await api.post<JobOut>(`/jobs/${id}/dismiss`)
      setExpandedId(null)
      setReloadKey((key) => key + 1)
    } catch (error) {
      setRowError(id, errorText(error, 'Could not dismiss this job.'))
    } finally {
      setBusyId(null)
    }
  }

  async function handleRestore(id: number) {
    if (busyId !== null) return
    setBusyId(id)
    setRowError(id, null)
    try {
      await api.post<JobOut>(`/jobs/${id}/restore`)
      setExpandedId(null)
      setReloadKey((key) => key + 1)
    } catch (error) {
      setRowError(id, errorText(error, 'Could not restore this job.'))
    } finally {
      setBusyId(null)
    }
  }

  async function handleApply(id: number, notes: string): Promise<boolean> {
    if (busyId !== null) return false
    setBusyId(id)
    setRowError(id, null)
    const body: { job_id: number; notes?: string } = { job_id: id }
    const trimmed = notes.trim()
    if (trimmed !== '') body.notes = trimmed
    try {
      await api.post<unknown>('/applications', body)
      setReloadKey((key) => key + 1)
      return true
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        if (error.detail === DISMISSED_DETAIL) {
          setRowError(id, DISMISSED_DETAIL)
        } else {
          setRowError(id, 'This job already has an application.')
          setReloadKey((key) => key + 1)
        }
      } else {
        setRowError(id, errorText(error, 'Could not mark this job as applied.'))
      }
      return false
    } finally {
      setBusyId(null)
    }
  }

  function handlePrevious() {
    setOffset((current) => Math.max(0, current - PAGE_SIZE))
    setExpandedId(null)
  }

  function handleNext() {
    setOffset((current) => (current + PAGE_SIZE >= total ? current : current + PAGE_SIZE))
    setExpandedId(null)
  }

  const activeCount = tab === 'active' ? total : otherTotal
  const dismissedCount = tab === 'dismissed' ? total : otherTotal

  return (
    <div>
      <PageHeader
        eyebrow="REVIEW QUEUE"
        title="Jobs to Apply"
        description="The AI suggests. You decide what happens next."
      />

      <JobsFilterBar filters={filters} onChange={handleFiltersChange} onClear={handleClear} />

      <div className="mt-6">
        {loadError !== null ? (
          <div className="rounded-card border border-line bg-surface shadow-card">
            <ErrorState message={loadError} onRetry={handleRetry} />
          </div>
        ) : (
          <JobsTable
            tab={tab}
            onTabChange={handleTabChange}
            jobs={jobs ?? []}
            loading={jobs === null}
            offset={offset}
            total={total}
            activeCount={activeCount}
            dismissedCount={dismissedCount}
            expandedId={expandedId}
            busy={busyId !== null}
            rowErrors={rowErrors}
            onToggle={handleToggle}
            onPrevious={handlePrevious}
            onNext={handleNext}
            onOpen={handleOpen}
            onDismiss={handleDismiss}
            onRestore={handleRestore}
            onApply={handleApply}
          />
        )}
      </div>
    </div>
  )
}
