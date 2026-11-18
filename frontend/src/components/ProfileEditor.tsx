import { formatDateTime } from '../lib/time'

type ProfileEditorProps = {
  value: string
  onChange: (value: string) => void
  updatedAt: string
  message: string | null
}

export default function ProfileEditor({
  value,
  onChange,
  updatedAt,
  message,
}: ProfileEditorProps) {
  const trimmedLength = value.trim().length
  const isOverLimit = value.length > 2000
  const saveDisabled = trimmedLength === 0 || trimmedLength > 2000

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-5">
      <h2 className="font-semibold text-neutral-900">Profile text</h2>
      <textarea
        aria-label="Profile text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={14}
        className="mt-3 w-full resize-y rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 focus:border-accent-500 focus:outline-none focus:ring-1 focus:ring-accent-500"
      />
      {message && <p className="mt-2 text-sm text-red-600">{message}</p>}
      <div className="mt-3 flex items-center justify-between text-sm">
        <span className={isOverLimit ? 'text-red-600' : 'text-neutral-500'}>
          {value.length} / 2000
        </span>
        <span className="text-neutral-500">Last saved {formatDateTime(updatedAt)}</span>
      </div>
      <button
        type="button"
        disabled={saveDisabled}
        className="mt-4 rounded-md bg-accent-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
      >
        Save
      </button>
    </div>
  )
}
