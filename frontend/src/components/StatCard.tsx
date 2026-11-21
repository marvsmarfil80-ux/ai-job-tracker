import type { ComponentType } from 'react'

type IconComponent = ComponentType<{ size?: number | string; className?: string }>

type StatCardProps = {
  label: string
  value: number
  icon: IconComponent
}

export default function StatCard({ label, value, icon: Icon }: StatCardProps) {
  return (
    <div className="flex items-center gap-4 rounded-card border border-line bg-surface p-5 shadow-card">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent-soft-ink">
        <Icon size={20} />
      </span>
      <div className="min-w-0">
        <p className="text-sm text-ink-muted">{label}</p>
        <p className="mt-1 text-3xl font-semibold text-ink">{value}</p>
      </div>
    </div>
  )
}
