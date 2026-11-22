import type { ComponentType } from 'react'

type IconComponent = ComponentType<{ size?: number | string; className?: string }>

const chips = {
  accent: 'bg-accent-soft text-accent-soft-ink',
  info: 'bg-info-soft text-info-ink',
  warn: 'bg-warn-soft text-warn-ink',
  ok: 'bg-ok-soft text-ok-ink',
} as const

type StatCardProps = {
  label: string
  value: number
  icon: IconComponent
  tone?: keyof typeof chips
}

export default function StatCard({ label, value, icon: Icon, tone = 'accent' }: StatCardProps) {
  return (
    <div className="flex items-center gap-4 rounded-card border border-line bg-surface p-5 shadow-card">
      <span
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${chips[tone]}`}
      >
        <Icon size={20} />
      </span>
      <div className="min-w-0">
        <p className="text-sm text-ink-muted">{label}</p>
        <p className="mt-1 text-3xl font-bold text-ink">{value}</p>
      </div>
    </div>
  )
}
