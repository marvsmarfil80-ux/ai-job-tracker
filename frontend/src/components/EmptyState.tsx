import { Inbox } from 'lucide-react'

type EmptyStateProps = {
  title: string
  hint: string
}

export default function EmptyState({ title, hint }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center px-4 py-10 text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-soft text-accent-soft-ink">
        <Inbox size={20} />
      </span>
      <p className="mt-3 font-semibold text-ink">{title}</p>
      <p className="mt-1 text-sm text-ink-muted">{hint}</p>
    </div>
  )
}
