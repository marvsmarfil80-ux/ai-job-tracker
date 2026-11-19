import { Play } from 'lucide-react'

type RunHuntCardProps = {
  busy: boolean
  running: boolean
  message: string | null
  notice?: string | null
  onRun: () => void
}

export default function RunHuntCard({
  busy,
  running,
  message,
  notice,
  onRun,
}: RunHuntCardProps) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-5">
      <h2 className="font-semibold text-neutral-900">Run Hunt</h2>
      <p className="mt-1 text-sm text-neutral-500">
        Fetches job feeds only. No AI is used.
      </p>

      <button
        type="button"
        onClick={onRun}
        disabled={busy || running}
        className="mt-4 inline-flex items-center gap-2 rounded-md bg-accent-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
      >
        <Play size={16} />
        {running ? 'Running...' : 'Run Hunt'}
      </button>

      {(busy || running) && (
        <p className="mt-3 text-sm text-neutral-600">A step is running. Please wait.</p>
      )}
      {message !== null && <p className="mt-3 text-sm text-red-600">{message}</p>}
      {notice !== null && notice !== undefined && (
        <p className="mt-3 text-sm text-neutral-600">{notice}</p>
      )}
    </div>
  )
}
