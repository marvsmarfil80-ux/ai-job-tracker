import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { JobOut } from '../types'
import { jobGridColumns, rangeText } from '../lib/jobs'
import JobRow from './JobRow'

export type JobsTab = 'active' | 'dismissed'

type JobsTableProps = {
  tab: JobsTab
  onTabChange: (tab: JobsTab) => void
  jobs: JobOut[]
  offset: number
  total: number
  activeCount: number
  dismissedCount: number
  expandedId: number | null
  onToggle: (id: number) => void
  onPrevious: () => void
  onNext: () => void
  onDismiss: (id: number) => void
  onRestore: (id: number) => void
  onApplied: (id: number) => void
}

const pagerButton =
  'inline-flex h-8 items-center gap-1 rounded-lg border border-control bg-surface px-2.5 text-xs font-medium text-ink enabled:hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50'

const tabBase =
  'inline-flex h-9 items-center gap-1.5 border-b-2 px-1 text-[13px] font-medium'

export default function JobsTable({
  tab,
  onTabChange,
  jobs,
  offset,
  total,
  activeCount,
  dismissedCount,
  expandedId,
  onToggle,
  onPrevious,
  onNext,
  onDismiss,
  onRestore,
  onApplied,
}: JobsTableProps) {
  return (
    <section className="rounded-card border border-line bg-surface p-5 shadow-card">
      <div className="flex items-center justify-between gap-4">
        <div role="tablist" aria-label="Job lists" className="flex items-center gap-4">
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
            <span className="text-xs font-normal text-ink-subtle">{activeCount}</span>
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
            <span className="text-xs font-normal text-ink-subtle">{dismissedCount}</span>
          </button>
        </div>
        <p className="text-[13px] text-ink-muted">{rangeText(offset, jobs.length, total)}</p>
      </div>

      <div className="mt-5 overflow-x-auto">
        <div className="min-w-[860px]">
          <div
            className={`${jobGridColumns} items-center rounded-lg bg-sunken px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-ink-subtle`}
          >
            <span className="whitespace-nowrap">Job</span>
            <span className="whitespace-nowrap">AI signal</span>
            <span className="whitespace-nowrap">Work mode</span>
            <span className="whitespace-nowrap">State</span>
            <span aria-hidden="true" />
          </div>

          {jobs.length === 0 ? (
            <p className="px-4 py-10 text-center text-[13px] text-ink-muted">
              No jobs in this tab.
            </p>
          ) : (
            <div className="mt-1 divide-y divide-line">
              {jobs.map((job) => (
                <JobRow
                  key={job.id}
                  job={job}
                  expanded={expandedId === job.id}
                  onToggle={() => onToggle(job.id)}
                  onDismiss={() => onDismiss(job.id)}
                  onRestore={() => onRestore(job.id)}
                  onApplied={() => onApplied(job.id)}
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
          disabled={offset === 0}
          className={pagerButton}
        >
          <ChevronLeft size={14} aria-hidden="true" />
          Previous
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={offset + jobs.length >= total}
          className={pagerButton}
        >
          Next
          <ChevronRight size={14} aria-hidden="true" />
        </button>
      </div>
    </section>
  )
}
