import { useState } from 'react'

type MarkAppliedFormProps = {
  jobTitle: string
  onConfirm: () => void
  onCancel: () => void
}

export default function MarkAppliedForm({ jobTitle, onConfirm, onCancel }: MarkAppliedFormProps) {
  const [notes, setNotes] = useState('')

  return (
    <div className="mt-4 rounded-lg border border-line bg-surface p-4">
      <label htmlFor="application-notes" className="text-xs font-medium text-ink-muted">
        Notes (optional)
      </label>
      <textarea
        id="application-notes"
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
        maxLength={2000}
        rows={3}
        className="mt-1 w-full rounded-lg border border-control bg-surface px-3 py-2 text-sm text-ink"
      />
      <p className="mt-1 text-right text-xs text-ink-subtle">{notes.length} / 2000</p>
      <p className="mt-1 text-xs text-ink-muted">
        This only records the application in this tracker. Nothing is sent to the employer.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onConfirm}
          aria-label={`Mark ${jobTitle} as applied`}
          className="inline-flex h-9 items-center rounded-lg bg-accent-600 px-3 text-sm font-medium text-white hover:bg-accent-700"
        >
          Mark as applied
        </button>
        <button
          type="button"
          onClick={onCancel}
          aria-label={`Cancel marking ${jobTitle} as applied`}
          className="inline-flex h-9 items-center rounded-lg border border-control bg-surface px-3 text-sm font-medium text-ink hover:bg-sunken"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
