import { useState } from 'react'
import type { ChangeEvent } from 'react'
import { Sparkles } from 'lucide-react'

type ScoreNewJobsCardProps = {
  running: boolean
  onScore: (limit: number) => void
}

function clampLimit(value: string): number {
  if (value.trim() === '') return 5
  const parsed = Number(value)
  if (Number.isNaN(parsed)) return 5
  return Math.min(20, Math.max(1, Math.trunc(parsed)))
}

export default function ScoreNewJobsCard({ running, onScore }: ScoreNewJobsCardProps) {
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
    <div className="inline-flex items-center gap-2">
      <input
        id="score-count"
        type="number"
        min={1}
        max={20}
        value={count}
        onChange={handleCountChange}
        onBlur={handleCountBlur}
        aria-label="Jobs to score"
        title="Jobs to score (1-20)"
        className="w-16 rounded-lg border border-control bg-surface px-2.5 py-2 text-sm text-ink focus-visible:border-focus"
      />
      <button
        type="button"
        onClick={handleScore}
        disabled={running}
        title="Uses AI (Groq). Counts toward the daily limit."
        className="inline-flex items-center gap-2 rounded-lg border border-control bg-surface px-4 py-2 text-sm font-medium text-ink enabled:hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Sparkles size={16} aria-hidden="true" />
        {running ? 'Scoring...' : 'Score New Jobs'}
      </button>
    </div>
  )
}
