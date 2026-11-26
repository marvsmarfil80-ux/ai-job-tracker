import { useState } from 'react'
import { Check, CircleAlert, ExternalLink, Pencil } from 'lucide-react'
import type { ApplicationChanges, ApplicationDetail, ApplicationStatus } from '../lib/applications'
import {
  HISTORY_TEXT,
  NOTES_MAX,
  applicationStatusLabel,
  applicationStatusTone,
  canDelete,
} from '../lib/applications'
import { sourceLabel } from '../lib/sources'
import { formatDateTime } from '../lib/time'
import StatusBadge from './StatusBadge'
import EmptyState from './EmptyState'
import StatusMenu from './StatusMenu'

export type DetailBusy = 'status' | 'notes' | 'delete'

type ApplicationDetailPanelProps = {
  detail: ApplicationDetail | null
  busy: DetailBusy | null
  disabled: boolean
  error: string | null
  onSave: (changes: ApplicationChanges) => Promise<boolean>
  onDelete: () => Promise<boolean>
}

type DetailBodyProps = Omit<ApplicationDetailPanelProps, 'detail'> & {
  detail: ApplicationDetail
}

const outlineButton =
  'inline-flex h-9 items-center gap-1.5 whitespace-nowrap rounded-lg border border-control bg-surface px-3 text-sm font-medium text-ink enabled:hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50'

const primaryButton =
  'inline-flex h-9 items-center whitespace-nowrap rounded-lg bg-accent-600 px-3 text-sm font-medium text-white enabled:hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50'

const dangerButton =
  'inline-flex h-9 items-center whitespace-nowrap rounded-lg border border-control bg-surface px-3 text-sm font-medium text-err-ink enabled:hover:bg-err-soft disabled:cursor-not-allowed disabled:opacity-50'

const confirmButton =
  'inline-flex h-9 items-center whitespace-nowrap rounded-lg bg-err-soft px-3 text-sm font-semibold text-err-ink disabled:cursor-not-allowed disabled:opacity-50'

const sectionLabel = 'text-xs font-semibold uppercase tracking-widest text-ink-muted'

function DetailBody({ detail, busy, disabled, error, onSave, onDelete }: DetailBodyProps) {
  const [draftStatus, setDraftStatus] = useState<ApplicationStatus>(detail.status)
  const [editingNotes, setEditingNotes] = useState(false)
  const [draftNotes, setDraftNotes] = useState(detail.notes ?? '')
  const [confirming, setConfirming] = useState(false)

  const statusChanged = draftStatus !== detail.status
  const trimmedNotes = draftNotes.trim()
  const notesChanged = trimmedNotes !== (detail.notes ?? '')
  const deletable = canDelete(detail)
  const history = [...detail.events].reverse()
  const notesId = `application-notes-${detail.id}`
  const notesHeadingId = `application-notes-heading-${detail.id}`

  function handleSaveStatus() {
    if (!statusChanged) return
    void onSave({ status: draftStatus })
  }

  function handleSaveNotes() {
    if (!notesChanged) return
    void onSave({ notes: trimmedNotes === '' ? null : trimmedNotes })
  }

  function handleCancelNotes() {
    setDraftNotes(detail.notes ?? '')
    setEditingNotes(false)
  }

  async function handleDelete() {
    const ok = await onDelete()
    if (!ok) setConfirming(false)
  }

  return (
    <section className="rounded-card border border-line bg-surface p-6 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className={sectionLabel}>Application detail</p>
          <h2 className="mt-1.5 text-xl font-bold tracking-tight text-ink">{detail.job.title}</h2>
          <p className="mt-1 text-sm text-ink-muted">
            {detail.job.company ?? 'Company not listed'} · via {sourceLabel(detail.job.source)}
          </p>
          <p className="mt-0.5 text-xs text-ink-subtle">Applied {formatDateTime(detail.applied_at)}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <a
            href={detail.job.url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Open listing for ${detail.job.title} in a new tab`}
            className={outlineButton}
          >
            Open listing
            <ExternalLink size={14} aria-hidden="true" />
          </a>
          {!editingNotes && (
            <button
              type="button"
              onClick={() => setEditingNotes(true)}
              disabled={disabled || statusChanged}
              className={outlineButton}
            >
              <Pencil size={14} aria-hidden="true" />
              Edit notes
            </button>
          )}
        </div>
      </div>

      <div className="mt-5 border-y border-line py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-ink-muted">Current status</p>
          <div className="flex items-center gap-2">
            <StatusBadge tone={applicationStatusTone(detail.status)}>
              {applicationStatusLabel(detail.status)}
            </StatusBadge>
            <StatusMenu value={draftStatus} disabled={disabled || editingNotes} onSelect={setDraftStatus} />
          </div>
        </div>

        {statusChanged && (
          <div className="mt-3 rounded-lg bg-sunken px-4 py-3">
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-sm text-ink">
                Change status to <span className="font-semibold">{applicationStatusLabel(draftStatus)}</span>?
              </p>
              <div className="ml-auto flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleSaveStatus}
                  disabled={disabled}
                  className={primaryButton}
                >
                  {busy === 'status' ? 'Saving...' : 'Save status'}
                </button>
                <button
                  type="button"
                  onClick={() => setDraftStatus(detail.status)}
                  disabled={disabled}
                  className={outlineButton}
                >
                  Cancel
                </button>
              </div>
            </div>
            {deletable && (
              <p className="mt-2 text-xs text-ink-muted">
                This adds a history entry, so this application can no longer be deleted.
              </p>
            )}
          </div>
        )}
      </div>

      <div className="mt-6">
        <h3 className={sectionLabel}>Status history</h3>
        <ol className="mt-3 space-y-4">
          {history.map((event) => (
            <li key={event.id} className="flex items-start gap-3">
              <span
                aria-hidden="true"
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent-soft-ink"
              >
                <Check size={14} />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink">{applicationStatusLabel(event.to_status)}</p>
                <p className="text-xs text-ink-subtle">
                  {event.from_status === null
                    ? 'Created'
                    : `From ${applicationStatusLabel(event.from_status)}`}{' '}
                  · {formatDateTime(event.changed_at)}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="mt-6">
        <div className="flex items-center justify-between gap-4">
          <h3 id={notesHeadingId} className={sectionLabel}>
            Notes
          </h3>
          {editingNotes && (
            <span className="text-xs tabular-nums text-ink-subtle">
              {draftNotes.length.toLocaleString('en-US')} / {NOTES_MAX.toLocaleString('en-US')}
            </span>
          )}
        </div>
        {editingNotes ? (
          <div>
            <textarea
              id={notesId}
              aria-labelledby={notesHeadingId}
              rows={5}
              maxLength={NOTES_MAX}
              value={draftNotes}
              onChange={(event) => setDraftNotes(event.target.value)}
              disabled={disabled}
              placeholder="Add notes about this application"
              className="mt-2 w-full resize-y rounded-lg border border-control bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-subtle disabled:cursor-not-allowed disabled:opacity-50"
            />
            <div className="mt-3 flex items-center gap-2">
              <button
                type="button"
                onClick={handleSaveNotes}
                disabled={!notesChanged || disabled}
                className={primaryButton}
              >
                {busy === 'notes' ? 'Saving...' : 'Save notes'}
              </button>
              <button
                type="button"
                onClick={handleCancelNotes}
                disabled={disabled}
                className={outlineButton}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <p
            className={`mt-2 whitespace-pre-line rounded-lg border border-line bg-surface px-4 py-3 text-sm ${
              detail.notes ? 'text-ink-muted' : 'text-ink-subtle'
            }`}
          >
            {detail.notes ?? 'No notes yet.'}
          </p>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-4 text-sm text-err-ink">
          {error}
        </p>
      )}

      <div className="mt-6 border-t border-line pt-5">
        {!deletable ? (
          <p className="flex items-start gap-2 rounded-lg bg-warn-soft px-4 py-3 text-sm text-warn-ink">
            <CircleAlert size={16} className="mt-0.5 shrink-0" aria-hidden="true" />
            {HISTORY_TEXT}
          </p>
        ) : confirming ? (
          <div className="rounded-lg bg-sunken p-4">
            <p className="text-sm text-ink">
              Delete this application? Its follow-ups are deleted too. This cannot be undone.
            </p>
            <div className="mt-3 flex items-center gap-2">
              <button
                type="button"
                onClick={handleDelete}
                disabled={disabled}
                className={confirmButton}
              >
                {busy === 'delete' ? 'Deleting...' : 'Delete'}
              </button>
              <button
                type="button"
                onClick={() => setConfirming(false)}
                disabled={disabled}
                className={outlineButton}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            disabled={disabled || statusChanged || editingNotes}
            className={dangerButton}
          >
            Delete application
          </button>
        )}
      </div>
    </section>
  )
}

export default function ApplicationDetailPanel(props: ApplicationDetailPanelProps) {
  if (props.detail === null) {
    return (
      <section className="rounded-card border border-line bg-surface shadow-card">
        <EmptyState
          title="No application selected."
          hint="Select an application to see its details."
        />
      </section>
    )
  }
  return <DetailBody {...props} detail={props.detail} />
}
