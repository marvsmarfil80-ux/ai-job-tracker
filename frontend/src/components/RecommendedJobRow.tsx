import { ArrowRight } from 'lucide-react'
import type { JobOut } from '../types'
import { sourceLabel } from '../lib/sources'

export default function RecommendedJobRow({ job }: { job: JobOut }) {
  return (
    <div className="flex items-start justify-between gap-4 py-4">
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-ink">{job.title}</p>
        <p className="mt-1 text-sm text-ink-muted">
          {job.company ?? 'Company not listed'}
          <span className="whitespace-nowrap">
            {' '}· via {sourceLabel(job.source)}{' '}
            <ArrowRight size={14} className="inline-block align-[-2px]" />
          </span>
        </p>
        {job.reason && (
          <p className="mt-2 line-clamp-2 text-sm text-ink-muted">{job.reason}</p>
        )}
      </div>
      <span className="shrink-0 rounded-lg bg-accent-soft px-2.5 py-1 text-sm font-semibold text-accent-soft-ink">
        {job.score ?? '-'}
      </span>
    </div>
  )
}
