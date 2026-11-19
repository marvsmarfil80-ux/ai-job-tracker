import { useState } from 'react'
import type { ChangeEvent } from 'react'
import { Sparkles } from 'lucide-react'
import type { ScoreRunResult } from '../types'

type ScoreNewJobsCardProps = {
  result: ScoreRunResult | null
}

export default function ScoreNewJobsCard({ result }: ScoreNewJobsCardProps) {
  const [count, setCount] = useState(5)

  function handleCountChange(event: ChangeEvent<HTMLInputElement>) {
    const parsed = Number(event.target.value)
    if (Number.isNaN(parsed)) {
      setCount(1)
      return
    }
    setCount(Math.min(20, Math.max(1, Math.trunc(parsed))))
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
            className="mt-1 w-24 rounded-md border border-neutral-300 px-3 py-1.5 text-sm text-neutral-900 focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-100"
          />
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-md bg-accent-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-700"
        >
          <Sparkles size={16} />
          Score
        </button>
      </div>

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
            <p className="mt-3 text-sm text-neutral-600">{result.stopped_reason}</p>
          )}
        </div>
      )}
    </div>
  )
}
