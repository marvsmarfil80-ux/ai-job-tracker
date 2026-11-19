import { ChevronLeft, ChevronRight } from 'lucide-react'
import { formatDateTime } from '../lib/time'
import { sourceLabel } from '../lib/sources'
import EmptyState from './EmptyState'
import type { HuntList, HuntRun, HuntStep } from '../types'

type HuntHistoryProps = {
  huntList: HuntList
  onPrevious: () => void
  onNext: () => void
  loading: boolean
}

const runStatusClasses: Record<HuntRun['status'], string> = {
  done: 'bg-accent-50 text-accent-700',
  running: 'bg-amber-50 text-amber-700',
  error: 'bg-red-50 text-red-700',
}

const stepStatusClasses: Record<HuntStep['status'], string> = {
  done: 'text-neutral-600',
  running: 'text-amber-700',
  error: 'text-red-600',
  skipped: 'text-neutral-500',
}

function stepLabel(source: string): string {
  return source === 'email' ? 'Email sync' : sourceLabel(source)
}

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
    <div className="rounded-lg border border-neutral-200 bg-white p-5">
      <h2 className="font-semibold text-neutral-900">Hunt history</h2>

      {isEmpty ? (
        <EmptyState title="No hunts yet." hint="Run a hunt to fetch jobs." />
      ) : (
        <>
          <div className="mt-2 divide-y divide-neutral-200">
            {huntList.items.map((run) => (
              <div key={run.id} className="py-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-3">
                    <p className="font-medium text-neutral-900">Run #{run.id}</p>
                    <span
                      className={`rounded-md px-2 py-0.5 text-xs font-medium capitalize ${runStatusClasses[run.status]}`}
                    >
                      {run.status}
                    </span>
                    <span className="text-sm text-neutral-500">{run.trigger}</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-4 text-sm text-neutral-600">
                    <span>{formatDateTime(run.started_at)}</span>
                    <span className="font-medium text-neutral-900">{run.total_new} new</span>
                  </div>
                </div>

                <ul className="mt-2 space-y-1">
                  {run.steps.map((step, index) => (
                    <li
                      key={`${run.id}-${step.source}-${index}`}
                      className="flex flex-wrap items-baseline gap-x-3 text-sm"
                    >
                      <span className="font-medium text-neutral-700">
                        {stepLabel(step.source)}
                      </span>
                      {step.status === 'skipped' ? (
                        <span className="text-neutral-500">Skipped: {step.message}</span>
                      ) : (
                        <span className={stepStatusClasses[step.status]}>{step.status}</span>
                      )}
                      {step.status !== 'skipped' && (
                        <>
                          <span className="text-neutral-500">found {step.found}</span>
                          <span className="text-neutral-500">new {step.new}</span>
                        </>
                      )}
                      {step.status !== 'skipped' && step.message !== null && (
                        <span className="text-neutral-600">{step.message}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-neutral-200 pt-4">
            <p className="text-sm text-neutral-600">
              Showing {start}-{end} of {huntList.total}
            </p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onPrevious}
                disabled={loading || huntList.offset === 0}
                className="inline-flex items-center gap-1 rounded-md border border-neutral-300 px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:cursor-not-allowed disabled:text-neutral-400"
              >
                <ChevronLeft size={16} />
                Previous
              </button>
              <button
                type="button"
                onClick={onNext}
                disabled={loading || nextDisabled}
                className="inline-flex items-center gap-1 rounded-md border border-neutral-300 px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:cursor-not-allowed disabled:text-neutral-400"
              >
                Next
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
