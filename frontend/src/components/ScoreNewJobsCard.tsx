import { useState } from 'react'
import type { ChangeEvent } from 'react'
import { Sparkles } from 'lucide-react'
import type { ScoreRunResult } from '../types'

type ScoreNewJobsCardProps = {
  running: boolean
  result: ScoreRunResult | null
  error: string | null
  onScore: (limit: number) => void
}

function clampLimit(value: string): number {
  if (value.trim() === '') return 5
  const parsed = Number(value)
  if (Number.isNaN(parsed)) return 5
  return Math.min(20, Math.max(1, Math.trunc(parsed)))
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

export default function ScoreNewJobsCard({
  running,
  result,
  error,
  onScore,
}: ScoreNewJobsCardProps) {
  const [count, setCount] = useState('5')

  function handleCountChange(event: ChangeEvent<HTMLInputElement>) {
    setCount(event.target.value)
  }

  function handleCountBlur() {
    setCount(String(clampLimit(count)))
  }

  function handleScore() {
    const limit = clampLimit(count)
    setCount(String(limit))
    onScore(limit)
  }

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-5">
      <h2 className="font-semibold text-neutral-900">Score New Jobs</h2>
      <p className="mt-1 text-sm text-neutral-500">
        Uses AI (Groq). Counts toward the daily limit.
      </p>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <div>
          <label
            htmlFor="score-count"
            className="block text-sm font-medium text-neutral-700"
          >
            Jobs to score
          </label>
          <input
            id="score-count"
            type="number"
            min={1}
            max={20}
            value={count}
            onChange={handleCountChange}
            onBlur={handleCountBlur}
            className="mt-1 w-24 rounded-md border border-neutral-300 px-3 py-1.5 text-sm text-neutral-900 focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-100"
          />
        </div>
        <button
          type="button"
          onClick={handleScore}
          disabled={running}
          className="inline-flex items-center gap-2 rounded-md bg-accent-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
        >
          <Sparkles size={16} />
          {running ? 'Scoring...' : 'Score'}
        </button>
      </div>

      {running && (
        <p className="mt-3 text-sm text-neutral-600">Scoring can take up to a minute.</p>
      )}
      {error !== null && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {result !== null && (
        <div className="mt-5 border-t border-neutral-200 pt-5">
          <dl className="grid grid-cols-3 gap-3 text-sm">
            <div>
              <dt className="text-neutral-500">Scored</dt>
              <dd className="mt-1 font-semibold text-neutral-900">{result.scored}</dd>
            </div>
            <div>
              <dt className="text-neutral-500">Failed</dt>
              <dd className="mt-1 font-semibold text-neutral-900">{result.failed}</dd>
            </div>
            <div>
              <dt className="text-neutral-500">Errored</dt>
              <dd className="mt-1 font-semibold text-neutral-900">{result.errored}</dd>
            </div>
          </dl>

          <dl className="mt-3 grid grid-cols-3 gap-3 text-sm">
            <div>
              <dt className="text-neutral-500">Title checked</dt>
              <dd className="mt-1 font-semibold text-neutral-900">
                {result.title_filter.checked}
              </dd>
            </div>
            <div>
              <dt className="text-neutral-500">Filtered out</dt>
              <dd className="mt-1 font-semibold text-neutral-900">
                {result.title_filter.filtered_out}
              </dd>
            </div>
            <div>
              <dt className="text-neutral-500">Passed</dt>
              <dd className="mt-1 font-semibold text-neutral-900">
                {result.title_filter.passed}
              </dd>
            </div>
          </dl>

          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-neutral-500">Cap used before</dt>
              <dd className="mt-1 font-semibold text-neutral-900">
                {result.cap.used_before}
              </dd>
            </div>
            <div>
              <dt className="text-neutral-500">Remaining after</dt>
              <dd className="mt-1 font-semibold text-neutral-900">
                {result.cap.remaining_after}
              </dd>
            </div>
          </dl>

          {result.stopped_reason !== null && (
            <p className="mt-3 text-sm text-neutral-600">
              {stoppedText(result.stopped_reason)}
            </p>
          )}
          {result.attempted === 0 && result.stopped_reason === null && (
            <p className="mt-3 text-sm text-neutral-600">No jobs were ready to score.</p>
          )}
        </div>
      )}
    </div>
  )
}
