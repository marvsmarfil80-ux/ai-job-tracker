import { formatDateTime } from '../lib/time'
import StatusBadge from './StatusBadge'

type ProfileEditorProps = {
  value: string
  onChange: (value: string) => void
  updatedAt: string
  message: string | null
  dirty: boolean
  showSaved: boolean
  showEmptyNotice: boolean
}

export default function ProfileEditor({
  value,
  onChange,
  updatedAt,
  message,
  dirty,
  showSaved,
  showEmptyNotice,
}: ProfileEditorProps) {
  const isOverLimit = value.length > 2000

  return (
    <div className="flex h-full flex-col rounded-card border border-line bg-surface p-6 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">Profile text</h2>
          <p className="mt-1 text-sm text-ink-muted">
            {updatedAt !== '' && <span>Last updated {formatDateTime(updatedAt)} · </span>}
            <span className={isOverLimit ? 'font-medium text-err-ink' : undefined}>
              {value.length.toLocaleString('en-US')} / 2,000 characters
            </span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {dirty && <StatusBadge tone="warn">Unsaved changes</StatusBadge>}
          {showSaved && updatedAt !== '' && <StatusBadge tone="ok">Saved</StatusBadge>}
        </div>
      </div>
      {showEmptyNotice && (
        <p className="mt-2 text-sm text-ink-muted">
          Your profile is empty. Write it here and press Save. Scoring does not run until a
          profile is saved.
        </p>
      )}
      <textarea
        aria-label="Profile text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-4 min-h-60 w-full flex-1 resize-y rounded-lg border border-control bg-surface px-3 py-2 text-sm text-ink focus:border-focus"
      />
      {message && <p className="mt-2 text-sm text-err-ink">{message}</p>}
      <p className="mt-3 text-sm text-ink-muted">Replaces the whole text when saved.</p>
    </div>
  )
}
