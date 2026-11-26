import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { JobOut } from '../types'
import { jobGridColumns, rangeText } from '../lib/jobs'
import JobRow from './JobRow'

export type JobsTab = 'active' | 'dismissed'

type JobsTableProps = {
  tab: JobsTab
  onTabChange: (tab: JobsTab) => void
  jobs: JobOut[]
  loading: boolean
  offset: number
  total: number
  activeCount: number
  dismissedCount: number
  expandedId: number | null
  busy: boolean
  rowErrors: Record<number, string>
  onToggle: (id: number) => void
  onPrevious: () => void
  onNext: () => void
  onOpen: (id: number) => void
  onDismiss: (id: number) => void
  onRestore: (id: number) => void
  onApply: (id: number, notes: string) => Promise<boolean>
}

const pagerButton =
  'inline-flex h-9 items-center gap-1 rounded-lg border border-control bg-surface px-3 text-sm font-medium text-ink enabled:hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50'

const tabBase = 'inline-flex h-10 items-center gap-2 border-b-2 px-1 text-sm font-semibold'

export default function JobsTable({
  tab,
  onTabChange,
  jobs,
  loading,
  offset,
  total,
  activeCount,
  dismissedCount,
  expandedId,
  busy,
  rowErrors,
  onToggle,
  onPrevious,
  onNext,
  onOpen,
  onDismiss,
  onRestore,
  onApply,
}: JobsTableProps) {
  return (
    <section className="rounded-card border border-line bg-surface p-6 shadow-card">
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
        <p className="text-xs text-ink-muted">{rangeText(offset, jobs.length, total)}</p>
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

          {jobs.length === 0 ? (
            <p className="px-4 py-10 text-center text-sm text-ink-muted">
              {loading ? 'Loading jobs.' : 'No jobs in this tab.'}
            </p>
          ) : (
            <div className="mt-1 divide-y divide-line">
              {jobs.map((job) => (
                <JobRow
                  key={job.id}
                  job={job}
                  expanded={expandedId === job.id}
                  busy={busy}
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

      <div className="mt-4 flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onPrevious}
          disabled={offset === 0 || busy}
          className={pagerButton}
        >
          <ChevronLeft size={14} aria-hidden="true" />
          Previous
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={offset + jobs.length >= total || busy}
          className={pagerButton}
        >
          Next
          <ChevronRight size={14} aria-hidden="true" />
        </button>
      </div>
    </section>
  )
}
