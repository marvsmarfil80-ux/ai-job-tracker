import { formatDateTime } from '../lib/time'
import { sourceLabel } from '../lib/sources'
import type { SourceInfo } from '../types'

type SourcesListProps = {
  sources: SourceInfo[]
}

export default function SourcesList({ sources }: SourcesListProps) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-5">
      <h2 className="font-semibold text-neutral-900">Sources</h2>

      <div className="mt-2 divide-y divide-neutral-200">
        {sources.map((source) => (
          <div
            key={source.id}
            className="flex flex-wrap items-center justify-between gap-3 py-4"
          >
            <div className="flex items-center gap-3">
              <p className="font-medium text-neutral-900">{sourceLabel(source.name)}</p>
              <span
                className={
                  source.enabled
                    ? 'rounded-md bg-accent-50 px-2 py-0.5 text-xs font-medium text-accent-700'
                    : 'rounded-md bg-neutral-100 px-2 py-0.5 text-xs font-medium text-neutral-600'
                }
              >
                {source.enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
            <div className="text-sm text-neutral-600">
              <p>
                Runs today: {source.runs_today} of {source.effective_max_runs_per_day}
              </p>
              <p className="mt-1">
                Last run: {source.last_run_at ? formatDateTime(source.last_run_at) : 'Never'}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
