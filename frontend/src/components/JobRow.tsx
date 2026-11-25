import { useState } from 'react'
import { ExternalLink, MoreHorizontal } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { JobOut } from '../types'
import type { Tone } from '../lib/hunt'
import { statusText } from '../lib/hunt'
import { sourceLabel } from '../lib/sources'
import { initialOf, jobGridColumns, pipelineLabel, verdictTone } from '../lib/jobs'
import { formatDate, formatDateTime } from '../lib/time'
import StatusBadge from './StatusBadge'
import MarkAppliedForm from './MarkAppliedForm'

type JobRowProps = {
  job: JobOut
  expanded: boolean
  onToggle: () => void
  onDismiss: () => void
  onRestore: () => void
  onApplied: () => void
}

const outlineButton =
  'inline-flex h-8 items-center gap-1.5 whitespace-nowrap rounded-lg border border-control bg-surface px-2.5 text-xs font-medium text-ink hover:bg-sunken'

const primaryButton =
  'inline-flex h-8 items-center rounded-lg bg-accent-600 px-2.5 text-xs font-medium text-white hover:bg-accent-700'

export default function JobRow({
  job,
  expanded,
  onToggle,
  onDismiss,
  onRestore,
  onApplied,
}: JobRowProps) {
  const [showForm, setShowForm] = useState(false)
  const detailsId = `job-details-${job.id}`

  const pipelineTone: Tone =
    job.pipeline_status === 'error'
      ? 'err'
      : job.pipeline_status === 'scored'
        ? 'ok'
        : job.pipeline_status === 'new'
          ? 'info'
          : 'idle'

  const dismissed = job.dismissed_at !== null
  const hasApplication = job.application_id !== null

  function handleToggle() {
    setShowForm(false)
    onToggle()
  }

  function handleConfirm() {
    setShowForm(false)
    onApplied()
  }

  return (
    <div>
      <div className={`${jobGridColumns} min-h-[76px] items-start px-4 py-4`}>
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-sm font-semibold text-accent-soft-ink">
            {initialOf(job)}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink">{job.title}</p>
            <p className="mt-0.5 flex min-w-0 items-center gap-1.5 overflow-hidden text-[13px] text-ink-muted">
              <span className="truncate">{job.company ?? 'Company not listed'}</span>
              <span className="shrink-0 text-ink-subtle" aria-hidden="true">
                ·
              </span>
              <span className="shrink-0 whitespace-nowrap">
                via {sourceLabel(job.source)}
              </span>
              {job.location && (
                <>
                  <span className="shrink-0 text-ink-subtle" aria-hidden="true">
                    ·
                  </span>
                  <span className="truncate">{job.location}</span>
                </>
              )}
            </p>
          </div>
        </div>

        <div className="min-w-0">
          {job.pipeline_status === 'new' ? (
            <p className="text-[13px] text-ink-muted">Not scored yet</p>
          ) : job.pipeline_status === 'filtered_out' || job.pipeline_status === 'error' ? (
            <div className="flex min-w-0 flex-col items-start gap-1">
              <StatusBadge tone={pipelineTone}>{pipelineLabel(job.pipeline_status)}</StatusBadge>
              {job.filter_reason && (
                <p className="w-full truncate text-[13px] text-ink-muted">{job.filter_reason}</p>
              )}
            </div>
          ) : (
            <div className="flex min-w-0 flex-col items-start gap-1">
              {job.score !== null && (
                <p className="text-xl font-bold leading-none tabular-nums text-accent-ink">
                  {job.score}
                </p>
              )}
              {job.verdict && (
                <StatusBadge tone={verdictTone(job.verdict)}>
                  {statusText(job.verdict)}
                </StatusBadge>
              )}
              {job.reason && (
                <p className="w-full truncate text-[13px] text-ink-muted">{job.reason}</p>
              )}
            </div>
          )}
        </div>

        <div>
          {job.work_mode ? (
            <span className="inline-flex w-fit items-center gap-1.5 whitespace-nowrap rounded-full bg-sunken px-2.5 py-0.5 text-xs font-medium text-ink-muted">
              <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-current" />
              {job.work_mode}
            </span>
          ) : (
            <span className="text-[13px] text-ink-subtle">—</span>
          )}
        </div>

        <div className="flex min-w-0 flex-col items-start gap-1">
          <StatusBadge tone={pipelineTone}>{pipelineLabel(job.pipeline_status)}</StatusBadge>
          {hasApplication ? (
            <StatusBadge tone="ok">Applied</StatusBadge>
          ) : job.opened_at ? (
            <p className="w-full truncate text-[13px] text-ink-muted">
              Opened {formatDate(job.opened_at)}
            </p>
          ) : null}
        </div>

        <div className="flex justify-start">
          <button
            type="button"
            onClick={handleToggle}
            aria-label={`More actions for ${job.title}`}
            aria-expanded={expanded}
            aria-controls={detailsId}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-ink-muted hover:bg-sunken hover:text-ink"
          >
            <MoreHorizontal size={18} aria-hidden="true" />
          </button>
        </div>
      </div>

      {expanded && (
        <div id={detailsId} className="mb-4 rounded-lg bg-sunken p-4">
          <div className="space-y-2.5 text-[13px] text-ink-muted">
            {job.description && (
              <p className="whitespace-pre-line text-ink-muted">{job.description}</p>
            )}
            <p>
              {job.opened_at ? `Opened ${formatDateTime(job.opened_at)}` : 'Not opened yet'}
            </p>
            {job.filter_reason && <p>Filter reason: {job.filter_reason}</p>}
            {job.red_flags && job.red_flags.length > 0 && (
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-ink-subtle">
                  Red flags
                </p>
                <ul className="mt-1 list-disc space-y-1 pl-5">
                  {job.red_flags.map((flag, index) => (
                    <li key={`${job.id}-flag-${index}`}>{flag}</li>
                  ))}
                </ul>
              </div>
            )}
            <p>
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Open listing link for ${job.title} in a new tab`}
                className="break-all text-accent-ink underline-offset-4 hover:underline"
              >
                {job.url}
              </a>
            </p>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Open listing for ${job.title} in a new tab`}
              className={outlineButton}
            >
              Open listing
              <ExternalLink size={14} aria-hidden="true" />
            </a>

            {dismissed ? (
              <button
                type="button"
                onClick={onRestore}
                aria-label={`Restore ${job.title}`}
                className={outlineButton}
              >
                Restore
              </button>
            ) : (
              !hasApplication && (
                <button
                  type="button"
                  onClick={onDismiss}
                  aria-label={`Dismiss ${job.title}`}
                  className={outlineButton}
                >
                  Dismiss
                </button>
              )
            )}

            {hasApplication ? (
              <Link
                to="/applications"
                aria-label={`View applications for ${job.title}`}
                className="text-xs font-medium text-accent-ink underline-offset-4 hover:underline"
              >
                View applications
              </Link>
            ) : dismissed ? (
              <p className="text-xs text-ink-muted">This job is dismissed. Restore it first.</p>
            ) : (
              <button
                type="button"
                onClick={() => setShowForm(true)}
                aria-label={`Open mark applied form for ${job.title}`}
                className={primaryButton}
              >
                Mark as applied
              </button>
            )}
          </div>

          {showForm && !hasApplication && !dismissed && (
            <MarkAppliedForm
              jobTitle={job.title}
              onConfirm={handleConfirm}
              onCancel={() => setShowForm(false)}
            />
          )}
        </div>
      )}
    </div>
  )
}
