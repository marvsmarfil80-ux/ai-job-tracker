import { useEffect, useRef, useState } from 'react'
import { Plus } from 'lucide-react'
import { ApiError } from '../types'
import PageHeader from '../components/PageHeader'
import ErrorState from '../components/ErrorState'
import FollowUpForm from '../components/FollowUpForm'
import FollowUpList, { FollowUpListSkeleton } from '../components/FollowUpList'
import type { ChoiceOption } from '../components/ChoiceMenu'
import {
  FOLLOW_UP_PAGE_SIZE,
  createFollowUp,
  deleteFollowUp,
  fetchApplicationOptions,
  fetchFollowUpCounts,
  fetchFollowUps,
  updateFollowUp,
  type FollowUpBusy,
  type FollowUpChanges,
  type FollowUpCounts,
  type FollowUpDetail,
  type FollowUpDraft,
  type FollowUpFilter,
} from '../lib/followUps'

const NETWORK_TEXT = 'Could not reach the server. Check that the backend is running, then try again.'

const GONE_TEXT = 'This follow-up no longer exists. The list was refreshed.'

const APPLICATION_GONE_TEXT = 'This application no longer exists. Choose another one.'

const cardClass = 'rounded-card border border-line bg-surface'

const primaryButton =
  'inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-lg bg-accent-600 px-4 text-sm font-medium text-white transition-colors duration-150 hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50'

const secondaryButton =
  'min-h-9 cursor-pointer rounded-lg border border-line bg-surface px-3 text-sm font-medium text-ink transition-colors duration-150 hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50'

type Loaded = {
  requestKey: string
  viewKey: string
  items: FollowUpDetail[]
  total: number
}

type LoadError = {
  requestKey: string
  message: string
}

type Notice = {
  message: string
  tone: 'err' | 'warn'
}

function errorText(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return NETWORK_TEXT
    if (error.status === 502 && error.detail === 'Request failed (502)') return NETWORK_TEXT
    if (error.validation !== null) return error.validation.map((item) => item.msg).join(' ')
    if (typeof error.detail === 'string' && error.detail !== '') return error.detail
  }
  return fallback
}

type SummaryCardProps = {
  label: string
  value: number | null
  hint: string
  warn?: boolean
}

function SummaryCard({ label, value, hint, warn = false }: SummaryCardProps) {
  return (
    <div className="rounded-card border border-line bg-surface p-5 shadow-card">
      <p className="text-xs font-semibold uppercase tracking-widest text-ink-subtle">{label}</p>
      <p
        className={`mt-2 text-3xl font-bold tracking-tight ${
          warn && value !== null && value > 0 ? 'text-warn-ink' : 'text-ink'
        }`}
      >
        {value ?? '-'}
      </p>
      <p className="mt-1 text-xs text-ink-muted">{hint}</p>
    </div>
  )
}

export default function FollowUps() {
  const [filter, setFilter] = useState<FollowUpFilter>('pending')
  const [offset, setOffset] = useState(0)
  const [reloadKey, setReloadKey] = useState(0)
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [loadError, setLoadError] = useState<LoadError | null>(null)
  const [counts, setCounts] = useState<FollowUpCounts | null>(null)
  const [busy, setBusy] = useState<FollowUpBusy>(null)
  const [creating, setCreating] = useState(false)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [applicationOptions, setApplicationOptions] = useState<ChoiceOption[] | null>(null)
  const [optionsError, setOptionsError] = useState<string | null>(null)
  const busyRef = useRef(false)

  const viewKey = filter
  const requestKey = `${filter}|${offset}|${reloadKey}`

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const page = await fetchFollowUps(filter, FOLLOW_UP_PAGE_SIZE, offset)
        if (cancelled) return
        if (page.items.length === 0 && offset > 0 && page.total > 0) {
          setOffset(Math.floor((page.total - 1) / FOLLOW_UP_PAGE_SIZE) * FOLLOW_UP_PAGE_SIZE)
          return
        }
        setLoaded({ requestKey, viewKey, items: page.items, total: page.total })
      } catch (error) {
        if (cancelled) return
        setLoadError({ requestKey, message: errorText(error, 'Could not load follow-ups.') })
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [filter, offset, requestKey, viewKey])

  useEffect(() => {
    let cancelled = false

    async function loadCounts() {
      try {
        const next = await fetchFollowUpCounts()
        if (!cancelled) setCounts(next)
      } catch {
        if (!cancelled) setCounts(null)
      }
    }

    loadCounts()

    return () => {
      cancelled = true
    }
  }, [reloadKey])

  const listError = loadError !== null && loadError.requestKey === requestKey ? loadError.message : null
  const busyActive = busy !== null || creating
  const listStatus: 'skeleton' | 'refreshing' | 'ready' =
    loaded !== null && loaded.requestKey === requestKey
      ? 'ready'
      : loaded !== null && loaded.viewKey === viewKey
        ? 'refreshing'
        : 'skeleton'
  const loadingText = listError === null && listStatus !== 'ready' ? 'Loading follow-ups.' : ''

  function reload() {
    setReloadKey((value) => value + 1)
  }

  function changeFilter(next: FollowUpFilter) {
    setFilter(next)
    setOffset(0)
    setNotice(null)
  }

  function handlePrevious() {
    setOffset((current) => Math.max(0, current - FOLLOW_UP_PAGE_SIZE))
    setNotice(null)
  }

  function handleNext() {
    const total = loaded?.total ?? 0
    setOffset((current) => (current + FOLLOW_UP_PAGE_SIZE >= total ? current : current + FOLLOW_UP_PAGE_SIZE))
    setNotice(null)
  }

  async function loadOptions() {
    setOptionsError(null)
    setApplicationOptions(null)
    try {
      const options = await fetchApplicationOptions()
      setApplicationOptions(options)
    } catch (error) {
      setOptionsError(errorText(error, 'Could not load applications.'))
    }
  }

  function openForm() {
    setFormOpen(true)
    setFormError(null)
    setNotice(null)
    loadOptions()
  }

  function closeForm() {
    setFormOpen(false)
    setFormError(null)
    setOptionsError(null)
  }

  async function runAction(
    next: NonNullable<FollowUpBusy>,
    action: () => Promise<unknown>,
    fallback: string,
  ): Promise<boolean> {
    if (busyRef.current) return false
    busyRef.current = true
    setBusy(next)
    setNotice(null)
    let ok = false
    try {
      await action()
      ok = true
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setNotice({ message: GONE_TEXT, tone: 'warn' })
      } else {
        setNotice({ message: errorText(error, fallback), tone: 'err' })
      }
    } finally {
      busyRef.current = false
      setBusy(null)
      reload()
    }
    return ok
  }

  function handleToggle(item: FollowUpDetail) {
    runAction(
      { id: item.id, kind: 'toggle' },
      () => updateFollowUp(item.id, { status: item.status === 'pending' ? 'completed' : 'pending' }),
      'Could not update this follow-up.',
    )
  }

  function handleSaveEdit(id: number, changes: FollowUpChanges): Promise<boolean> {
    return runAction({ id, kind: 'edit' }, () => updateFollowUp(id, changes), 'Could not save this follow-up.')
  }

  function handleDelete(id: number): Promise<boolean> {
    return runAction({ id, kind: 'delete' }, () => deleteFollowUp(id), 'Could not delete this follow-up.')
  }

  async function handleCreate(draft: FollowUpDraft): Promise<boolean> {
    if (busyRef.current) return false
    busyRef.current = true
    setCreating(true)
    setFormError(null)
    setNotice(null)
    let ok = false
    try {
      await createFollowUp(draft)
      ok = true
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setFormError(APPLICATION_GONE_TEXT)
      } else {
        setFormError(errorText(error, 'Could not save this follow-up.'))
      }
    } finally {
      busyRef.current = false
      setCreating(false)
    }
    if (ok) {
      setFormOpen(false)
      setFilter('pending')
      setOffset(0)
      reload()
    }
    return ok
  }

  function renderForm() {
    if (!formOpen) return null
    if (optionsError !== null) {
      return (
        <section className={`mb-6 ${cardClass}`}>
          <ErrorState message={optionsError} onRetry={loadOptions} />
          <div className="flex justify-center pb-6">
            <button type="button" onClick={closeForm} className={secondaryButton}>
              Cancel
            </button>
          </div>
        </section>
      )
    }
    if (applicationOptions === null) {
      return (
        <section aria-busy="true" className={`mb-6 p-6 ${cardClass}`}>
          <p role="status" className="text-sm text-ink-muted">
            Loading applications.
          </p>
        </section>
      )
    }
    return (
      <FollowUpForm
        applications={applicationOptions}
        saving={creating}
        error={formError}
        onSave={handleCreate}
        onCancel={closeForm}
      />
    )
  }

  function renderList() {
    if (listError !== null) {
      return (
        <section className={cardClass}>
          <ErrorState message={listError} onRetry={reload} />
        </section>
      )
    }
    if (loaded === null || listStatus === 'skeleton') {
      return <FollowUpListSkeleton />
    }
    return (
      <FollowUpList
        items={loaded.items}
        filter={filter}
        offset={offset}
        total={loaded.total}
        disabled={busyActive || listStatus !== 'ready'}
        refreshing={listStatus === 'refreshing'}
        busy={busy}
        onFilterChange={changeFilter}
        onToggle={handleToggle}
        onSaveEdit={handleSaveEdit}
        onDelete={handleDelete}
        onAdd={openForm}
        onPrevious={handlePrevious}
        onNext={handleNext}
      />
    )
  }

  return (
    <div>
      <PageHeader
        eyebrow="SIMPLE TO-DO LIST"
        title="Follow-ups"
        description="Reminders you set for your applications."
        actions={
          <button type="button" onClick={openForm} disabled={formOpen || busyActive} className={primaryButton}>
            <Plus size={16} aria-hidden="true" />
            Add follow-up
          </button>
        }
      />
      <section aria-label="Follow-up summary" className="mb-6 grid gap-4 sm:grid-cols-3">
        <SummaryCard label="Open" value={counts?.open ?? null} hint="Pending follow-ups" />
        <SummaryCard label="Overdue" value={counts?.overdue ?? null} hint="Due date has passed" warn />
        <SummaryCard label="Completed" value={counts?.completed ?? null} hint="Marked done" />
      </section>
      <p role="status" className="sr-only">
        {loadingText}
      </p>
      {renderForm()}
      {notice !== null && (
        <p
          role={notice.tone === 'err' ? 'alert' : 'status'}
          className={`mb-4 rounded-lg px-4 py-3 text-sm ${
            notice.tone === 'err' ? 'bg-err-soft text-err-ink' : 'bg-warn-soft text-warn-ink'
          }`}
        >
          {notice.message}
        </p>
      )}
      {renderList()}
    </div>
  )
}
