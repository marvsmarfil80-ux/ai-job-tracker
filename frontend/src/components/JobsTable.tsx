import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { JobOut } from '../types'
import { jobGridColumns, rangeText } from '../lib/jobs'
import JobRow from './JobRow'
import type { BusyState } from './JobRow'
import EmptyState from './EmptyState'
import SkeletonBlock from './SkeletonBlock'

export type JobsTab = 'active' | 'dismissed'

export type TableStatus = 'skeleton' | 'refreshing' | 'ready'

type JobsTableProps = {
  tab: JobsTab
  onTabChange: (tab: JobsTab) => void
  jobs: JobOut[]
  status: TableStatus
  offset: number
  total: number
  activeCount: number
  dismissedCount: number
  expandedId: number | null
  busy: BusyState | null
  disabled: boolean
  filtersActive: boolean
  rowErrors: Record<number, string>
  onToggle: (id: number) => void
  onPrevious: () => void
  onNext: () => void
  onOpen: (id: number) => void
  onDismiss: (id: number) => void
  onRestore: (id: number) => void
  onApply: (id: number, notes: string) => Promise<boolean>
  onClearFilters: () => void
}

const pagerButton =
  'inline-flex h-9 items-center gap-1 rounded-lg border border-control bg-surface px-3 text-sm font-medium text-ink enabled:hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50'

const tabBase = 'inline-flex h-10 items-center gap-2 border-b-2 px-1 text-sm font-semibold'

const skeletonRows = [0, 1, 2, 3, 4]

function SkeletonRows() {
  return (
    <div aria-hidden="true" className="mt-1 divide-y divide-line">
      {skeletonRows.map((row) => (
        <div key={row} className={`${jobGridColumns} min-h-[88px] items-start px-4 py-5`}>
          <div className="flex min-w-0 items-start gap-3">
            <SkeletonBlock className="h-9 w-9 shrink-0" />
            <div className="min-w-0 flex-1 space-y-2">
              <SkeletonBlock className="h-4 w-3/4" />
              <SkeletonBlock className="h-3 w-1/2" />
            </div>
          </div>
          <div className="flex flex-col items-start gap-2">
            <SkeletonBlock className="h-5 w-10" />
            <SkeletonBlock className="h-5 w-16" />
          </div>
          <SkeletonBlock className="h-5 w-16" />
          <SkeletonBlock className="h-5 w-14" />
          <SkeletonBlock className="h-9 w-9" />
        </div>
      ))}
    </div>
  )
}

export default function JobsTable({
  tab,
  onTabChange,
  jobs,
  status,
  offset,
  total,
  activeCount,
  dismissedCount,
  expandedId,
  busy,
  disabled,
  filtersActive,
  rowErrors,
  onToggle,
  onPrevious,
  onNext,
  onOpen,
  onDismiss,
  onRestore,
  onApply,
  onClearFilters,
}: JobsTableProps) {
  const showPager = status !== 'skeleton' && total > 0

  function renderEmpty() {
    if (filtersActive) {
      return (
        <EmptyState
          title="No jobs match these filters."
          hint="Try a different search or clear the filters."
          action={
            <button type="button" onClick={onClearFilters} className={pagerButton}>
              Clear filters
            </button>
          }
        />
      )
    }
    if (tab === 'dismissed') {
      return <EmptyState title="No dismissed jobs." hint="Jobs you dismiss will appear here." />
    }
    return (
      <EmptyState
        title="No active jobs yet."
        hint="Run a hunt to discover new jobs."
        action={
          <Link
            to="/job-hunter"
            className="text-sm font-medium text-accent-ink underline-offset-4 hover:underline"
          >
            Go to Job Hunter
          </Link>
        }
      />
    )
  }

  return (
    <section className="rounded-card border border-line bg-surface p-6 shadow-card">
      <p role="status" className="sr-only">
        {status === 'ready' ? '' : 'Loading jobs.'}
      </p>

      <div className="flex items-center justify-between gap-4">
        <div role="tablist" aria-label="Job lists" className="flex items-center gap-5">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'active'}
            onClick={() => onTabChange('active')}
            className={`${tabBase} ${
              tab === 'active'
                ? 'border-accent-600 text-ink'
                : 'border-transparent text-ink-muted hover:text-ink'
            }`}
          >
            Active
            <span className="text-xs font-semibold text-ink-subtle">{activeCount}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'dismissed'}
            onClick={() => onTabChange('dismissed')}
            className={`${tabBase} ${
              tab === 'dismissed'
                ? 'border-accent-600 text-ink'
                : 'border-transparent text-ink-muted hover:text-ink'
            }`}
          >
            Dismissed
            <span className="text-xs font-semibold text-ink-subtle">{dismissedCount}</span>
          </button>
        </div>
        {showPager && (
          <p className="text-xs text-ink-muted">{rangeText(offset, jobs.length, total)}</p>
        )}
      </div>

      <div className="mt-5 overflow-x-auto">
        <div className="min-w-[860px]">
          <div
            className={`${jobGridColumns} items-center rounded-lg bg-sunken px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-ink-muted`}
          >
            <span className="whitespace-nowrap">Job</span>
            <span className="whitespace-nowrap">AI signal</span>
            <span className="whitespace-nowrap">Work mode</span>
            <span className="whitespace-nowrap">State</span>
            <span aria-hidden="true" />
          </div>

          {status === 'skeleton' ? (
            <SkeletonRows />
          ) : jobs.length === 0 ? (
            renderEmpty()
          ) : (
            <div
              aria-busy={status === 'refreshing'}
              className={`mt-1 divide-y divide-line transition-opacity duration-150 ${
                status === 'refreshing' ? 'opacity-60' : ''
              }`}
            >
              {jobs.map((job) => (
                <JobRow
                  key={job.id}
                  job={job}
                  expanded={expandedId === job.id}
                  busyAction={busy !== null && busy.id === job.id ? busy.action : null}
                  disabled={disabled}
                  error={rowErrors[job.id] ?? null}
                  onToggle={() => onToggle(job.id)}
                  onOpen={() => onOpen(job.id)}
                  onDismiss={() => onDismiss(job.id)}
                  onRestore={() => onRestore(job.id)}
                  onApply={(notes) => onApply(job.id, notes)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {showPager && (
        <div className="mt-4 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onPrevious}
            disabled={offset === 0 || disabled}
            className={pagerButton}
          >
            <ChevronLeft size={14} aria-hidden="true" />
            Previous
          </button>
          <button
            type="button"
            onClick={onNext}
            disabled={offset + jobs.length >= total || disabled}
            className={pagerButton}
          >
            Next
            <ChevronRight size={14} aria-hidden="true" />
          </button>
        </div>
      )}
    </section>
  )
}
