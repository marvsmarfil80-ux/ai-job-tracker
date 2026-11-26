import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { ApiError } from '../types'
import type { JobList, JobOut } from '../types'
import PageHeader from '../components/PageHeader'
import ErrorState from '../components/ErrorState'
import JobsFilterBar from '../components/JobsFilterBar'
import type { JobFilters } from '../components/JobsFilterBar'
import JobsTable from '../components/JobsTable'
import type { JobsTab, TableStatus } from '../components/JobsTable'
import type { BusyAction, BusyState } from '../components/JobRow'
import { PAGE_SIZE } from '../lib/jobs'

const initialFilters: JobFilters = {
  search: '',
  verdict: '',
  pipeline: '',
  sort: '',
  openedOnly: false,
}

const DISMISSED_DETAIL = 'This job is dismissed. Restore it first.'
const APPLIED_DETAIL = 'This job already has an application.'
const NETWORK_TEXT = 'Could not reach the server. Check that the backend is running, then try again.'
const NOT_FOUND_TEXT = 'This job no longer exists.'

type Loaded = {
  requestKey: string
  viewKey: string
  tab: JobsTab
  items: JobOut[]
  total: number
  otherTotal: number
}

type LoadError = {
  requestKey: string
  message: string
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return NETWORK_TEXT
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
  const [reloadKey, setReloadKey] = useState(0)
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [loadError, setLoadError] = useState<LoadError | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [busy, setBusy] = useState<BusyState | null>(null)
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({})
  const [notice, setNotice] = useState<string | null>(null)
  const busyRef = useRef(false)

  const { verdict, pipeline, sort, openedOnly } = filters
  const viewKey = JSON.stringify([tab, verdict, pipeline, sort, openedOnly, search])
  const requestKey = `${viewKey}|${offset}|${reloadKey}`

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
        setLoaded({
          requestKey,
          viewKey,
          tab,
          items: list.items,
          total: list.total,
          otherTotal: other.total,
        })
      } catch (error) {
        if (cancelled) return
        setLoadError({ requestKey, message: errorText(error, 'Could not load jobs.') })
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [tab, verdict, pipeline, sort, openedOnly, search, offset, requestKey, viewKey])

  const errorMessage =
    loadError !== null && loadError.requestKey === requestKey ? loadError.message : null

  const status: TableStatus =
    loaded !== null && loaded.requestKey === requestKey
      ? 'ready'
      : loaded !== null && loaded.viewKey === viewKey
        ? 'refreshing'
        : 'skeleton'

  const jobs = status === 'skeleton' || loaded === null ? [] : loaded.items
  const total = status === 'skeleton' || loaded === null ? 0 : loaded.total
  const activeCount =
    loaded === null ? 0 : loaded.tab === 'active' ? loaded.total : loaded.otherTotal
  const dismissedCount =
    loaded === null ? 0 : loaded.tab === 'dismissed' ? loaded.total : loaded.otherTotal
  const filtersActive = search !== '' || verdict !== '' || pipeline !== '' || openedOnly

  function handleRetry() {
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
      setNotice(null)
    }
  }

  function handleClear() {
    setFilters(initialFilters)
    setSearch('')
    setOffset(0)
    setExpandedId(null)
    setNotice(null)
  }

  function handleTabChange(next: JobsTab) {
    setTab(next)
    setOffset(0)
    setExpandedId(null)
    setNotice(null)
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

  function handleActionError(id: number, error: unknown, fallback: string, isApply: boolean) {
    if (error instanceof ApiError && error.status === 404) {
      setRowError(id, null)
      setExpandedId(null)
      setNotice(NOT_FOUND_TEXT)
      setReloadKey((key) => key + 1)
      return
    }
    if (isApply && error instanceof ApiError && error.status === 409) {
      if (error.detail === DISMISSED_DETAIL) {
        setRowError(id, DISMISSED_DETAIL)
      } else {
        setRowError(id, APPLIED_DETAIL)
        setReloadKey((key) => key + 1)
      }
      return
    }
    setRowError(id, errorText(error, fallback))
  }

  async function runAction(
    id: number,
    action: BusyAction,
    fallback: string,
    request: () => Promise<unknown>,
  ): Promise<boolean> {
    if (busyRef.current) return false
    busyRef.current = true
    setBusy({ id, action })
    setNotice(null)
    setRowError(id, null)
    try {
      await request()
      setReloadKey((key) => key + 1)
      return true
    } catch (error) {
      handleActionError(id, error, fallback, action === 'apply')
      return false
    } finally {
      busyRef.current = false
      setBusy(null)
    }
  }

  async function handleOpen(id: number) {
    setRowError(id, null)
    try {
      const updated = await api.post<JobOut>(`/jobs/${id}/open`)
      setLoaded((current) =>
        current === null
          ? current
          : { ...current, items: current.items.map((job) => (job.id === id ? updated : job)) },
      )
    } catch (error) {
      handleActionError(id, error, 'Could not record that the listing was opened.', false)
    }
  }

  async function handleDismiss(id: number) {
    const ok = await runAction(id, 'dismiss', 'Could not dismiss this job.', () =>
      api.post<JobOut>(`/jobs/${id}/dismiss`),
    )
    if (ok) setExpandedId(null)
  }

  async function handleRestore(id: number) {
    const ok = await runAction(id, 'restore', 'Could not restore this job.', () =>
      api.post<JobOut>(`/jobs/${id}/restore`),
    )
    if (ok) setExpandedId(null)
  }

  function handleApply(id: number, notes: string): Promise<boolean> {
    const body: { job_id: number; notes?: string } = { job_id: id }
    const trimmed = notes.trim()
    if (trimmed !== '') body.notes = trimmed
    return runAction(id, 'apply', 'Could not mark this job as applied.', () =>
      api.post<unknown>('/applications', body),
    )
  }

  function handlePrevious() {
    setOffset((current) => Math.max(0, current - PAGE_SIZE))
    setExpandedId(null)
    setNotice(null)
  }

  function handleNext() {
    setOffset((current) => (current + PAGE_SIZE >= total ? current : current + PAGE_SIZE))
    setExpandedId(null)
    setNotice(null)
  }

  return (
    <div>
      <PageHeader
        eyebrow="REVIEW QUEUE"
        title="Jobs to Apply"
        description="The AI suggests. You decide what happens next."
      />

      <JobsFilterBar filters={filters} onChange={handleFiltersChange} onClear={handleClear} />

      <div className="mt-6">
        {notice !== null && (
          <p role="status" className="mb-4 rounded-lg bg-warn-soft px-4 py-3 text-sm text-warn-ink">
            {notice}
          </p>
        )}
        {errorMessage !== null ? (
          <div className="rounded-card border border-line bg-surface shadow-card">
            <ErrorState message={errorMessage} onRetry={handleRetry} />
          </div>
        ) : (
          <JobsTable
            tab={tab}
            onTabChange={handleTabChange}
            jobs={jobs}
            status={status}
            offset={offset}
            total={total}
            activeCount={activeCount}
            dismissedCount={dismissedCount}
            expandedId={expandedId}
            busy={busy}
            disabled={busy !== null || status !== 'ready'}
            filtersActive={filtersActive}
            rowErrors={rowErrors}
            onToggle={handleToggle}
            onPrevious={handlePrevious}
            onNext={handleNext}
            onOpen={handleOpen}
            onDismiss={handleDismiss}
            onRestore={handleRestore}
            onApply={handleApply}
            onClearFilters={handleClear}
          />
        )}
      </div>
    </div>
  )
}
