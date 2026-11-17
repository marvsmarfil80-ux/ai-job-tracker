import type { ComponentType } from 'react'

type IconComponent = ComponentType<{ size?: number | string; className?: string }>

type StatCardProps = {
  label: string
  value: number
  icon: IconComponent
}

export default function StatCard({ label, value, icon: Icon }: StatCardProps) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-neutral-500">{label}</p>
          <p className="mt-2 text-3xl font-semibold text-neutral-900">{value}</p>
        </div>
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-50 text-accent-600">
          <Icon size={20} />
        </span>
      </div>
    </div>
  )
}
