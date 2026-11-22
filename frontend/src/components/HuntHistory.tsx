import { ChevronLeft, ChevronRight } from 'lucide-react'
import { formatDateTime } from '../lib/time'
import { runTones, statusText, stepLabel } from '../lib/hunt'
import EmptyState from './EmptyState'
import StatusBadge from './StatusBadge'
import type { HuntList } from '../types'

type HuntHistoryProps = {
  huntList: HuntList
  onPrevious: () => void
  onNext: () => void
  loading: boolean
}

const pagerButton =
  'inline-flex items-center gap-1 rounded-lg border border-control bg-surface px-3 py-1.5 text-sm font-medium text-ink enabled:hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50'

export default function HuntHistory({
  huntList,
  onPrevious,
  onNext,
  loading,
}: HuntHistoryProps) {
  const start = huntList.items.length === 0 ? huntList.offset : huntList.offset + 1
  const end = huntList.offset + huntList.items.length
  const nextDisabled = huntList.offset + huntList.items.length >= huntList.total
  const isEmpty = huntList.total === 0 && huntList.items.length === 0

  return (
    <section className="rounded-card border border-line bg-surface p-6 shadow-card">
      <p className="text-xs font-semibold uppercase tracking-widest text-ink-subtle">
        Recent activity
      </p>
      <h2 className="mt-2 text-xl font-semibold text-ink">Hunt history</h2>

      {isEmpty ? (
        <EmptyState title="No hunts yet." hint="Run a hunt to fetch jobs." />
      ) : (
        <>
          <ul className="mt-3 divide-y divide-line">
            {huntList.items.map((run) => {
              const issues = run.steps.filter((step) => step.status !== 'done')
              return (
                <li key={run.id} className="py-3.5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-ink">Run #{run.id}</p>
                      <p className="text-xs text-ink-muted">
                        {run.total_new} new · {formatDateTime(run.started_at)} · {run.trigger}
                      </p>
                    </div>
                    <StatusBadge tone={runTones[run.status]}>{statusText(run.status)}</StatusBadge>
                  </div>
                  {issues.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {issues.map((step, index) => (
                        <li
                          key={`${run.id}-${step.source}-${index}`}
                          className="text-xs text-ink-muted"
                        >
                          <span className="font-medium text-ink">{stepLabel(step.source)}</span>
                          {': '}
                          {step.status === 'skipped'
                            ? `Skipped: ${step.message}`
                            : `${statusText(step.status)}${step.message !== null ? ` - ${step.message}` : ''}`}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              )
            })}
          </ul>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
            <p className="text-sm text-ink-muted">
              Showing {start}-{end} of {huntList.total}
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onPrevious}
                disabled={loading || huntList.offset === 0}
                className={pagerButton}
              >
                <ChevronLeft size={16} aria-hidden="true" />
                Previous
              </button>
              <button
                type="button"
                onClick={onNext}
                disabled={loading || nextDisabled}
                className={pagerButton}
              >
                Next
                <ChevronRight size={16} aria-hidden="true" />
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  )
}
