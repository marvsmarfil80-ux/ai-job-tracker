import { CircleAlert } from 'lucide-react'

type ErrorStateProps = {
  message: string
  onRetry: () => void
}

export default function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div role="alert" className="flex flex-col items-center px-4 py-10 text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-err-soft text-err-ink">
        <CircleAlert size={20} />
      </span>
      <p className="mt-3 text-sm text-ink">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 min-h-9 rounded-lg bg-accent-600 px-4 text-sm font-medium text-white transition-colors duration-150 hover:bg-accent-700"
      >
        Retry
      </button>
    </div>
  )
}
