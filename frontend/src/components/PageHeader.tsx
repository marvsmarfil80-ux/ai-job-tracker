import type { ReactNode } from 'react'

type PageHeaderProps = {
  eyebrow?: string
  title: string
  description?: string
  actions?: ReactNode
}

export default function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && (
          <p className="text-xs font-semibold uppercase tracking-widest text-ink-subtle">
            {eyebrow}
          </p>
        )}
        <h1 className="mt-1.5 text-3xl font-bold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1.5 text-sm text-ink-muted">{description}</p>}
      </div>
      {actions}
    </header>
  )
}
