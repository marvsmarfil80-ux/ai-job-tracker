import { formatDateTime } from '../lib/time'
import StatusBadge from './StatusBadge'

type ProfileEditorProps = {
  value: string
  onChange: (value: string) => void
  updatedAt: string
  message: string | null
  onSave: () => void
  saving: boolean
  dirty: boolean
  showSaved: boolean
  showEmptyNotice: boolean
}

export default function ProfileEditor({
  value,
  onChange,
  updatedAt,
  message,
  onSave,
  saving,
  dirty,
  showSaved,
  showEmptyNotice,
}: ProfileEditorProps) {
  const trimmedLength = value.trim().length
  const isOverLimit = value.length > 2000
  const saveDisabled = trimmedLength === 0 || trimmedLength > 2000 || saving

  return (
    <div className="rounded-card border border-line bg-surface p-5 shadow-card">
      <h2 className="text-base font-semibold text-ink">Profile text</h2>
      {showEmptyNotice && (
        <p className="mt-1 text-sm text-ink-muted">
          Your profile is empty. Write it here and press Save. Scoring does not run until a
          profile is saved.
        </p>
      )}
      <textarea
        aria-label="Profile text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={14}
        className="mt-3 w-full resize-y rounded-lg border border-control bg-surface px-3 py-2 text-sm text-ink focus:border-focus"
      />
      {message && <p className="mt-2 text-sm text-err-ink">{message}</p>}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className={isOverLimit ? 'font-medium text-err-ink' : 'text-ink-muted'}>
          {value.length} / 2000
        </span>
        {dirty && <StatusBadge tone="warn">Unsaved changes</StatusBadge>}
        {updatedAt !== '' && (
          <span className="text-ink-muted">Last saved {formatDateTime(updatedAt)}</span>
        )}
      </div>
      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={onSave}
          disabled={saveDisabled}
          className="min-h-9 rounded-lg bg-accent-600 px-4 text-sm font-medium text-white transition-colors duration-150 enabled:hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-line disabled:text-ink-subtle"
        >
          Save
        </button>
        {showSaved && updatedAt !== '' && (
          <StatusBadge tone="ok">Saved {formatDateTime(updatedAt)}</StatusBadge>
        )}
      </div>
    </div>
  )
}
