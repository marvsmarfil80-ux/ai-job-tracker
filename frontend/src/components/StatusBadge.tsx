import type { ReactNode } from 'react'

const tones = {
  ok: 'bg-ok-soft text-ok-ink',
  warn: 'bg-warn-soft text-warn-ink',
  err: 'bg-err-soft text-err-ink',
  info: 'bg-info-soft text-info-ink',
  idle: 'bg-idle-soft text-idle-ink',
} as const

type StatusBadgeProps = {
  tone: keyof typeof tones
  children: ReactNode
}

export default function StatusBadge({ tone, children }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex w-fit items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}
    >
      <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-current" />
      {children}
    </span>
  )
}
