import { ArrowRight } from 'lucide-react'
import type { JobOut } from '../types'
import { sourceLabel } from '../lib/sources'

export default function RecommendedJobRow({ job, rank }: { job: JobOut; rank: number }) {
  return (
    <div className="flex items-start gap-3 py-4 sm:gap-4">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sunken text-sm font-semibold text-ink-muted">
        {rank}
      </span>
      <div className="min-w-0 flex-1">
        <p className="break-words font-semibold text-ink">{job.title}</p>
        <p className="mt-1 break-words text-sm text-ink-muted">
          {job.company ?? 'Company not listed'}
          <span className="whitespace-nowrap">
            {' '}· via {sourceLabel(job.source)}{' '}
            <ArrowRight size={14} className="inline-block align-[-2px]" />
          </span>
        </p>
        {job.reason && (
          <p className="mt-2 line-clamp-2 break-words text-sm text-ink-muted">{job.reason}</p>
        )}
      </div>
      <span className="shrink-0 text-xl font-bold text-accent-ink">{job.score ?? '-'}</span>
    </div>
  )
}
