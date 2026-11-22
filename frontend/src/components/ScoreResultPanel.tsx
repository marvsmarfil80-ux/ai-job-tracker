import type { ScoreRunResult } from '../types'

type ScoreResultPanelProps = {
  result: ScoreRunResult | null
}

const stoppedMessages: Record<string, string> = {
  daily_cap_reached: 'Stopped: the daily AI limit was reached.',
  rate_limited: 'Stopped: the AI service is busy. Try again in a minute.',
  groq_unavailable: 'Stopped: the AI service is unavailable.',
  groq_auth_error: 'Stopped: the AI service rejected our credentials.',
}

function stoppedText(value: string): string {
  return stoppedMessages[value] ?? `Stopped: ${value}`
}

export default function ScoreResultPanel({ result }: ScoreResultPanelProps) {
  if (result === null) return null

  const stats: { label: string; value: number }[] = [
    { label: 'Scored', value: result.scored },
    { label: 'Failed', value: result.failed },
    { label: 'Errored', value: result.errored },
    { label: 'Title checked', value: result.title_filter.checked },
    { label: 'Filtered out', value: result.title_filter.filtered_out },
    { label: 'Passed', value: result.title_filter.passed },
    { label: 'Cap used before', value: result.cap.used_before },
    { label: 'Remaining after', value: result.cap.remaining_after },
  ]

  return (
    <section className="mb-6 rounded-card border border-line bg-surface p-5 shadow-card">
      <p className="text-xs font-semibold uppercase tracking-widest text-ink-subtle">
        Score result
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-3 min-[1050px]:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-lg bg-sunken px-3 py-2.5">
            <dt className="text-xs text-ink-muted">{stat.label}</dt>
            <dd className="mt-1 text-lg font-semibold tabular-nums text-ink">{stat.value}</dd>
          </div>
        ))}
      </dl>
      {result.stopped_reason !== null && (
        <p className="mt-4 text-sm text-ink-muted">{stoppedText(result.stopped_reason)}</p>
      )}
      {result.attempted === 0 && result.stopped_reason === null && (
        <p className="mt-4 text-sm text-ink-muted">No jobs were ready to score.</p>
      )}
    </section>
  )
}
