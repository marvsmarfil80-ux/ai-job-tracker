import { Mail, Rss } from 'lucide-react'
import StatusBadge from './StatusBadge'
import { formatDateTime } from '../lib/time'
import { formatDuration, runTones, statusText, stepLabel, stepTones } from '../lib/hunt'
import type { HuntRun } from '../types'

type LatestRunCardProps = {
  run: HuntRun
}

export default function LatestRunCard({ run }: LatestRunCardProps) {
  const found = run.steps.reduce(
    (sum, step) => (step.status === 'skipped' ? sum : sum + step.found),
    0,
  )
  const duration = formatDuration(run.started_at, run.finished_at)

  const stats: { label: string; value: string }[] = [
    { label: 'new jobs', value: String(run.total_new) },
    { label: 'found', value: String(found) },
    { label: 'duration', value: duration ?? '-' },
  ]

  return (
    <section className="rounded-card border border-line bg-surface p-6 shadow-card">
      <p className="text-xs font-semibold uppercase tracking-widest text-ink-subtle">
        Latest run
      </p>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold text-ink">
          Run #{run.id} · {formatDateTime(run.started_at)}
        </h2>
        <StatusBadge tone={runTones[run.status]}>{statusText(run.status)}</StatusBadge>
      </div>

      <dl className="mt-5 flex flex-wrap gap-x-12 gap-y-3 border-y border-line py-5">
        {stats.map((stat) => (
          <div key={stat.label} className="flex flex-col-reverse">
            <dt className="text-xs text-ink-muted">{stat.label}</dt>
            <dd className="text-3xl font-bold tabular-nums text-ink">{stat.value}</dd>
          </div>
        ))}
      </dl>

      <ul className="mt-2 divide-y divide-line">
        {run.steps.map((step, index) => (
          <li
            key={`${run.id}-${step.source}-${index}`}
            className="flex items-center gap-3 py-3.5"
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent-soft-ink">
              {step.source === 'email' ? (
                <Mail size={16} aria-hidden="true" />
              ) : (
                <Rss size={16} aria-hidden="true" />
              )}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-ink">{stepLabel(step.source)}</p>
              <p className="text-xs text-ink-muted">
                {step.status === 'skipped'
                  ? `Skipped: ${step.message}`
                  : `found ${step.found} · new ${step.new}`}
                {step.status !== 'skipped' && step.message !== null ? ` · ${step.message}` : ''}
              </p>
            </div>
            <StatusBadge tone={stepTones[step.status]}>{statusText(step.status)}</StatusBadge>
          </li>
        ))}
      </ul>
    </section>
  )
}
