import { CircleAlert } from 'lucide-react'

type ErrorStateProps = {
  message: string
  onRetry: () => void
}

export default function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div role="alert" className="flex flex-col items-center px-4 py-10 text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-neutral-100 text-neutral-600">
        <CircleAlert size={20} />
      </span>
      <p className="mt-3 text-sm text-neutral-700">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 rounded-md bg-accent-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-700"
      >
        Retry
      </button>
    </div>
  )
}
