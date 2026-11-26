import { useEffect, useRef, useState } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import { api } from '../lib/api'
import { ApiError } from '../types'
import PageHeader from '../components/PageHeader'
import ErrorState from '../components/ErrorState'
import ApplicationsFilterBar from '../components/ApplicationsFilterBar'
import type { ApplicationFilters } from '../components/ApplicationsFilterBar'
import ApplicationList from '../components/ApplicationList'
import ApplicationDetailPanel from '../components/ApplicationDetailPanel'
import type { DetailBusy } from '../components/ApplicationDetailPanel'
import type {
  ApplicationChanges,
  ApplicationDetail,
  ApplicationList as ApplicationListResponse,
  ApplicationOut,
} from '../lib/applications'
import { APPLICATION_PAGE_SIZE } from '../lib/applications'

const initialFilters: ApplicationFilters = { search: '', status: '' }

const NETWORK_TEXT = 'Could not reach the server. Check that the backend is running, then try again.'
const GONE_TEXT = 'This application no longer exists.'
const DELETED_TEXT = 'Application deleted.'

type Loaded = {
  requestKey: string
  viewKey: string
  items: ApplicationOut[]
  total: number
}

type LoadError = {
  requestKey: string
  message: string
}

type LoadedDetail = {
  requestKey: string
  data: ApplicationDetail
}

type Notice = {
  message: string
  tone: 'ok' | 'warn'
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return NETWORK_TEXT
    if (error.validation !== null) return error.validation.map((item) => item.msg).join(' ')
    if (typeof error.detail === 'string' && error.detail !== '') return error.detail
  }
  return fallback
}

function toSummary(detail: ApplicationDetail): ApplicationOut {
  return {
    id: detail.id,
    job_id: detail.job_id,
    status: detail.status,
    applied_at: detail.applied_at,
    notes: detail.notes,
    job: detail.job,
  }
}

const cardClass = 'rounded-card border border-line bg-surface shadow-card'

export default function Applications() {
  const [filters, setFilters] = useState<ApplicationFilters>(initialFilters)
  const [showFilters, setShowFilters] = useState(false)
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [reloadKey, setReloadKey] = useState(0)
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [loadError, setLoadError] = useState<LoadError | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detailReloadKey, setDetailReloadKey] = useState(0)
  const [detail, setDetail] = useState<LoadedDetail | null>(null)
  const [detailError, setDetailError] = useState<LoadError | null>(null)
  const [version, setVersion] = useState(0)
  const [busy, setBusy] = useState<DetailBusy | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)
  const busyRef = useRef(false)

  const status = filters.status
  const viewKey = JSON.stringify([status, search])
  const requestKey = `${viewKey}|${offset}|${reloadKey}`
  const detailKey = `${selectedId ?? 'none'}|${detailReloadKey}`

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

    async function load() {
      try {
        const list = await api.get<ApplicationListResponse>('/applications', {
          limit: APPLICATION_PAGE_SIZE,
          offset,
          status,
          q: search,
        })
        if (cancelled) return
        if (list.items.length === 0 && offset > 0 && list.total > 0) {
          setOffset(Math.floor((list.total - 1) / APPLICATION_PAGE_SIZE) * APPLICATION_PAGE_SIZE)
          return
        }
        setLoaded({ requestKey, viewKey, items: list.items, total: list.total })
        setSelectedId((current) => current ?? list.items[0]?.id ?? null)
      } catch (error) {
        if (cancelled) return
        setLoadError({ requestKey, message: errorText(error, 'Could not load applications.') })
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [status, search, offset, requestKey, viewKey])

  useEffect(() => {
    if (selectedId === null) return
    let cancelled = false
    const id = selectedId
    const key = detailKey

    async function loadDetail() {
      try {
        const data = await api.get<ApplicationDetail>(`/applications/${id}`)
        if (!cancelled) setDetail({ requestKey: key, data })
      } catch (error) {
        if (cancelled) return
        if (error instanceof ApiError && error.status === 404) {
          setSelectedId(null)
          setNotice({ message: GONE_TEXT, tone: 'warn' })
          setReloadKey((value) => value + 1)
          return
        }
        setDetailError({ requestKey: key, message: errorText(error, 'Could not load this application.') })
      }
    }

    loadDetail()

    return () => {
      cancelled = true
    }
  }, [selectedId, detailKey])

  const listError = loadError !== null && loadError.requestKey === requestKey ? loadError.message : null
  const items = loaded?.items ?? []
  const total = loaded?.total ?? 0
  const selectedDetail = detail !== null && detail.requestKey === detailKey ? detail.data : null
  const detailErrorMessage =
    detailError !== null && detailError.requestKey === detailKey ? detailError.message : null
  const filtersActive = search !== '' || status !== ''
  const activeFilterCount = (filters.search.trim() !== '' ? 1 : 0) + (status !== '' ? 1 : 0)
  const busyActive = busy !== null

  function handleFiltersChange(next: ApplicationFilters) {
    const changed = next.status !== filters.status
    setFilters(next)
    if (changed) {
      setOffset(0)
      setNotice(null)
    }
  }

  function handleClear() {
    setFilters(initialFilters)
    setSearch('')
    setOffset(0)
    setNotice(null)
  }

  function handleSelect(id: number) {
    setSelectedId(id)
    setActionError(null)
    setNotice(null)
  }

  function handlePrevious() {
    setOffset((current) => Math.max(0, current - APPLICATION_PAGE_SIZE))
    setNotice(null)
  }

  function handleNext() {
    setOffset((current) =>
      current + APPLICATION_PAGE_SIZE >= total ? current : current + APPLICATION_PAGE_SIZE,
    )
    setNotice(null)
  }

  function handleGone() {
    setSelectedId(null)
    setActionError(null)
    setNotice({ message: GONE_TEXT, tone: 'warn' })
    setReloadKey((value) => value + 1)
  }

  async function handleSave(changes: ApplicationChanges): Promise<boolean> {
    if (selectedId === null || busyRef.current) return false
    const id = selectedId
    const key = detailKey
    busyRef.current = true
    setBusy(changes.status !== undefined ? 'status' : 'notes')
    setActionError(null)
    setNotice(null)
    try {
      const updated = await api.patch<ApplicationDetail>(`/applications/${id}`, changes)
      setDetail({ requestKey: key, data: updated })
      setLoaded((current) =>
        current === null
          ? current
          : {
              ...current,
              items: current.items.map((item) => (item.id === id ? toSummary(updated) : item)),
            },
      )
      setVersion((value) => value + 1)
      setReloadKey((value) => value + 1)
      return true
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        handleGone()
        return false
      }
      setActionError(errorText(error, 'Could not save the changes.'))
      return false
    } finally {
      busyRef.current = false
      setBusy(null)
    }
  }

  async function handleDelete(): Promise<boolean> {
    if (selectedId === null || busyRef.current) return false
    const id = selectedId
    busyRef.current = true
    setBusy('delete')
    setActionError(null)
    setNotice(null)
    try {
      await api.delete<void>(`/applications/${id}`)
      setSelectedId(null)
      setNotice({ message: DELETED_TEXT, tone: 'ok' })
      setReloadKey((value) => value + 1)
      return true
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        handleGone()
        return false
      }
      setActionError(errorText(error, 'Could not delete this application.'))
      return false
    } finally {
      busyRef.current = false
      setBusy(null)
    }
  }

  function renderList() {
    if (listError !== null) {
      return (
        <section className={cardClass}>
          <ErrorState message={listError} onRetry={() => setReloadKey((value) => value + 1)} />
        </section>
      )
    }
    if (loaded === null) {
      return (
        <section className={`${cardClass} px-5 py-10 text-center text-sm text-ink-muted`}>
          Loading applications...
        </section>
      )
    }
    return (
      <ApplicationList
        items={items}
        offset={offset}
        total={total}
        selectedId={selectedId}
        disabled={busyActive}
        filtersActive={filtersActive}
        onSelect={handleSelect}
        onPrevious={handlePrevious}
        onNext={handleNext}
        onClearFilters={handleClear}
      />
    )
  }

  function renderDetail() {
    if (selectedId === null) {
      return (
        <ApplicationDetailPanel
          detail={null}
          busy={null}
          disabled={false}
          error={null}
          onSave={handleSave}
          onDelete={handleDelete}
        />
      )
    }
    if (detailErrorMessage !== null) {
      return (
        <section className={cardClass}>
          <ErrorState
            message={detailErrorMessage}
            onRetry={() => setDetailReloadKey((value) => value + 1)}
          />
        </section>
      )
    }
    if (selectedDetail === null) {
      return (
        <section className={`${cardClass} px-5 py-10 text-center text-sm text-ink-muted`}>
          Loading application...
        </section>
      )
    }
    return (
      <ApplicationDetailPanel
        key={`${selectedDetail.id}-${version}`}
        detail={selectedDetail}
        busy={busy}
        disabled={busyActive}
        error={actionError}
        onSave={handleSave}
        onDelete={handleDelete}
      />
    )
  }

  return (
    <div>
      <PageHeader
        eyebrow="PIPELINE"
        title="Applications"
        description="Track where each application stands and keep notes in one place."
        actions={
          <button
            type="button"
            onClick={() => setShowFilters((value) => !value)}
            aria-expanded={showFilters}
            aria-controls="application-filters"
            className="inline-flex h-10 items-center gap-2 whitespace-nowrap rounded-lg border border-control bg-surface px-3.5 text-sm font-medium text-ink hover:bg-sunken"
          >
            <SlidersHorizontal size={15} aria-hidden="true" />
            Filter applications
            {activeFilterCount > 0 && (
              <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-accent-600 px-1.5 text-xs font-semibold text-white">
                {activeFilterCount}
              </span>
            )}
          </button>
        }
      />

      {showFilters && (
        <div id="application-filters" className="mb-6">
          <ApplicationsFilterBar filters={filters} onChange={handleFiltersChange} onClear={handleClear} />
        </div>
      )}

      {notice !== null && (
        <p
          role="status"
          className={`mb-4 rounded-lg px-4 py-3 text-sm ${
            notice.tone === 'ok' ? 'bg-ok-soft text-ok-ink' : 'bg-warn-soft text-warn-ink'
          }`}
        >
          {notice.message}
        </p>
      )}

      <div className="grid items-start gap-6 min-[1050px]:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        {renderList()}
        <div className="min-[1050px]:sticky min-[1050px]:top-6">{renderDetail()}</div>
      </div>
    </div>
  )
}
