import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ApplicationOut } from '../lib/applications'
import { applicationStatusLabel, applicationStatusTone } from '../lib/applications'
import { rangeText } from '../lib/jobs'
import { sourceLabel } from '../lib/sources'
import { formatDate } from '../lib/time'
import StatusBadge from './StatusBadge'
import EmptyState from './EmptyState'

type ApplicationListProps = {
  items: ApplicationOut[]
  offset: number
  total: number
  selectedId: number | null
  disabled: boolean
  filtersActive: boolean
  onSelect: (id: number) => void
  onPrevious: () => void
  onNext: () => void
  onClearFilters: () => void
}

const pagerButton =
  'inline-flex h-9 items-center gap-1 rounded-lg border border-control bg-surface px-3 text-sm font-medium text-ink enabled:hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50'

function initialFor(item: ApplicationOut): string {
  const basis = item.job.company?.trim() || item.job.title.trim()
  return basis.charAt(0).toUpperCase() || '?'
}

export default function ApplicationList({
  items,
  offset,
  total,
  selectedId,
  disabled,
  filtersActive,
  onSelect,
  onPrevious,
  onNext,
  onClearFilters,
}: ApplicationListProps) {
  const showPager = total > 0

  function renderEmpty() {
    if (filtersActive) {
      return (
        <EmptyState
          title="No applications match these filters."
          hint="Try a different search or clear the filters."
          action={
            <button type="button" onClick={onClearFilters} className={pagerButton}>
              Clear filters
            </button>
          }
        />
      )
    }
    return (
      <EmptyState
        title="No applications yet."
        hint="Mark a job as applied on Jobs to Apply to track it here."
        action={
          <Link
            to="/jobs"
            className="text-sm font-medium text-accent-ink underline-offset-4 hover:underline"
          >
            Go to Jobs to Apply
          </Link>
        }
      />
    )
  }

  return (
    <section className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
      <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-4">
        <p className="text-sm font-semibold text-ink">
          {total} {total === 1 ? 'application' : 'applications'}
        </p>
        <p className="text-xs text-ink-subtle">Newest first</p>
      </div>

      {items.length === 0 ? (
        renderEmpty()
      ) : (
        <ul aria-label="Applications" className="divide-y divide-line">
          {items.map((item) => {
            const selected = item.id === selectedId
            return (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => onSelect(item.id)}
                  disabled={disabled}
                  aria-current={selected ? 'true' : undefined}
                  className={`flex w-full items-center gap-3 border-l-2 px-5 py-4 text-left transition-colors duration-150 disabled:cursor-not-allowed ${
                    selected ? 'border-accent-600 bg-sunken' : 'border-transparent hover:bg-sunken'
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-sm font-bold text-accent-soft-ink"
                  >
                    {initialFor(item)}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-ink">{item.job.title}</span>
                    <span className="mt-0.5 flex min-w-0 items-center gap-1.5 overflow-hidden text-xs text-ink-muted">
                      <span className="truncate">{item.job.company ?? 'Company not listed'}</span>
                      <span className="shrink-0" aria-hidden="true">
                        ·
                      </span>
                      <span className="shrink-0 whitespace-nowrap">via {sourceLabel(item.job.source)}</span>
                    </span>
                    <span className="mt-0.5 block text-xs text-ink-muted">
                      Applied {formatDate(item.applied_at)}
                    </span>
                  </span>
                  <StatusBadge tone={applicationStatusTone(item.status)}>
                    {applicationStatusLabel(item.status)}
                  </StatusBadge>
                </button>
              </li>
            )
          })}
        </ul>
      )}

      {showPager && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3">
          <p className="text-xs text-ink-muted">{rangeText(offset, items.length, total)}</p>
          <div className="flex items-center gap-2">
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
              disabled={offset + items.length >= total || disabled}
              className={pagerButton}
            >
              Next
              <ChevronRight size={14} aria-hidden="true" />
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
