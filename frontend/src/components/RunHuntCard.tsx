import { Play } from 'lucide-react'

type RunHuntCardProps = {
  busy: boolean
  running: boolean
  onRun: () => void
}

export default function RunHuntCard({ busy, running, onRun }: RunHuntCardProps) {
  return (
    <button
      type="button"
      onClick={onRun}
      disabled={busy || running}
      title="Fetches job feeds only. No AI is used."
      className="inline-flex items-center gap-2 rounded-lg border border-transparent bg-accent-600 px-4 py-2 text-sm font-medium text-white enabled:hover:bg-accent-700 disabled:cursor-not-allowed disabled:border-line disabled:bg-sunken disabled:text-ink-muted"
    >
      <Play size={16} aria-hidden="true" />
      {running ? 'Running...' : 'Run Hunt'}
    </button>
  )
}
