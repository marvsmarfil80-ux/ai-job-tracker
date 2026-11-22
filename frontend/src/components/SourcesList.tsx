import { Rss } from 'lucide-react'
import { formatDateTime } from '../lib/time'
import { sourceLabel } from '../lib/sources'
import EmptyState from './EmptyState'
import StatusBadge from './StatusBadge'
import type { SourceInfo } from '../types'

type SourcesListProps = {
  sources: SourceInfo[]
}

export default function SourcesList({ sources }: SourcesListProps) {
  return (
    <section className="rounded-card border border-line bg-surface p-6 shadow-card">
      <p className="text-xs font-semibold uppercase tracking-widest text-ink-subtle">
        Connected sources
      </p>
      <h2 className="mt-2 text-xl font-semibold text-ink">Sources</h2>

      {sources.length === 0 ? (
        <EmptyState title="No sources are configured." hint="" />
      ) : (
        <div className="mt-2 divide-y divide-line">
          {sources.map((source) => (
            <div
              key={source.id}
              className="flex flex-wrap items-center justify-between gap-3 py-4"
            >
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent-soft-ink">
                  <Rss size={16} aria-hidden="true" />
                </span>
                <p className="font-medium text-ink">{sourceLabel(source.name)}</p>
                <StatusBadge tone={source.enabled ? 'ok' : 'idle'}>
                  {source.enabled ? 'Enabled' : 'Disabled'}
                </StatusBadge>
              </div>
              <div className="text-sm text-ink-muted">
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
      )}
    </section>
  )
}
