import { useId, useState } from 'react'

type MarkAppliedFormProps = {
  jobTitle: string
  busy: boolean
  onConfirm: (notes: string) => void
  onCancel: () => void
}

export default function MarkAppliedForm({
  jobTitle,
  busy,
  onConfirm,
  onCancel,
}: MarkAppliedFormProps) {
  const [notes, setNotes] = useState('')
  const notesId = useId()

  return (
    <div className="mt-4 rounded-lg border border-line bg-surface p-4">
      <label htmlFor={notesId} className="text-sm font-medium text-ink-muted">
        Notes (optional)
      </label>
      <textarea
        id={notesId}
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
        maxLength={2000}
        rows={3}
        className="mt-1 w-full rounded-lg border border-control bg-surface px-3 py-2 text-sm text-ink"
      />
      <p className="mt-1 text-right text-xs text-ink-subtle">{notes.length} / 2000</p>
      <p className="mt-1 text-sm text-ink-muted">
        This only records the application in this tracker. Nothing is sent to the employer.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onConfirm(notes)}
          disabled={busy}
          aria-label={`Mark as applied: ${jobTitle}`}
          className="inline-flex h-9 items-center rounded-lg bg-accent-600 px-3 text-sm font-medium text-white enabled:hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Mark as applied
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          aria-label={`Cancel marking ${jobTitle} as applied`}
          className="inline-flex h-9 items-center rounded-lg border border-control bg-surface px-3 text-sm font-medium text-ink enabled:hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
