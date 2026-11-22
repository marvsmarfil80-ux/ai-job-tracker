import { useState } from 'react'
import { Upload } from 'lucide-react'
import type { ChangeEvent } from 'react'
import type { ResumeDraftOut } from '../types'

type ResumeDraftCardProps = {
  draft: ResumeDraftOut | null
  busy: boolean
  error: { status: number; detail: string } | null
  onCreate: (file: File) => void
  onClearError: () => void
  onAddDraft: () => void
  addMessage: string | null
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${Math.round(bytes / 1024)} KiB`
  return `${(bytes / 1048576).toFixed(1)} MiB`
}

export default function ResumeDraftCard({
  draft,
  busy,
  error,
  onCreate,
  onClearError,
  onAddDraft,
  addMessage,
}: ResumeDraftCardProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState('')

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    onClearError()
    const file = event.target.files?.[0]

    if (!file) {
      setSelectedFile(null)
      setFileError('')
      return
    }

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setFileError('Only PDF files are supported.')
      setSelectedFile(null)
      event.target.value = ''
      return
    }

    if (file.size > 2097152) {
      setFileError('The PDF is too large. Maximum size is 2 MiB.')
      setSelectedFile(null)
      event.target.value = ''
      return
    }

    setFileError('')
    setSelectedFile(file)
  }

  const droppedSkills =
    draft === null
      ? ''
      : Array.isArray(draft.dropped_skills)
        ? draft.dropped_skills.join(', ')
        : String(draft.dropped_skills)

  return (
    <div className="rounded-card border border-line bg-surface p-5 shadow-card">
      <p className="text-xs font-semibold uppercase tracking-widest text-ink-subtle">
        Suggestion only
      </p>
      <h2 className="mt-1 text-base font-semibold text-ink">Resume draft</h2>
      <p className="mt-1 text-sm text-ink-muted">
        Your PDF text is sent to Groq, a third party, after emails, phone numbers and contact
        lines are removed. Names, employers, schools and job titles are not removed.
      </p>

      <div className="mt-4 rounded-xl border border-dashed border-control bg-sunken p-4 text-center">
        <div className="flex flex-col items-center gap-1">
          <Upload size={20} className="text-accent-ink" aria-hidden="true" />
          <p className="text-sm font-semibold text-accent-ink">Upload a resume PDF</p>
          <p className="text-xs text-ink-muted">Up to 2 MiB · 5 drafts per day</p>
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-center gap-3">
          <input
            aria-label="Resume PDF"
            type="file"
            accept="application/pdf,.pdf"
            onChange={handleFileChange}
            disabled={busy}
            className="block min-w-0 text-sm text-ink-muted file:mr-3 file:rounded-lg file:border-0 file:bg-surface file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink hover:file:bg-line"
          />
          <button
            type="button"
            onClick={() => {
              if (selectedFile) onCreate(selectedFile)
            }}
            disabled={!selectedFile || busy}
            className="min-h-9 rounded-lg bg-accent-600 px-4 text-sm font-medium text-white transition-colors duration-150 enabled:hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-line disabled:text-ink-subtle"
          >
            Create draft
          </button>
        </div>
      </div>

      {busy && (
        <p className="mt-2 text-sm text-ink-muted">
          Reading your PDF and asking Groq. This can take a while.
        </p>
      )}
      {error && (
        <>
          <p className="mt-2 text-sm text-err-ink">{error.detail}</p>
          {error.status === 429 && error.detail === 'Daily resume draft limit reached.' && (
            <p className="mt-1 text-sm text-ink-muted">
              Resume drafts are limited to 5 per day (UTC), shared with job scoring.
            </p>
          )}
        </>
      )}
      {fileError && <p className="mt-2 text-sm text-err-ink">{fileError}</p>}
      {selectedFile && (
        <p className="mt-2 text-sm text-ink-muted">
          {selectedFile.name} ({formatFileSize(selectedFile.size)})
        </p>
      )}

      {draft !== null && (
        <div className="mt-5 border-t border-line pt-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-ink-subtle">
            Skills found
          </p>
          <div className="flex flex-wrap gap-1.5">
            {draft.skills.map((skill, index) => (
              <span
                key={`${skill}-${index}`}
                className="rounded-lg bg-accent-soft px-2.5 py-1 text-sm font-medium text-accent-soft-ink"
              >
                {skill}
              </span>
            ))}
          </div>

          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-ink-muted">Pages</dt>
              <dd className="mt-1 font-semibold text-ink">{draft.pages}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">Extracted chars</dt>
              <dd className="mt-1 font-semibold text-ink">{draft.extracted_chars}</dd>
            </div>
            <div>
              <dt className="text-ink-muted">Truncated</dt>
              <dd className="mt-1 font-semibold text-ink">
                {draft.truncated ? 'Yes' : 'No'}
              </dd>
            </div>
            <div>
              <dt className="text-ink-muted">Dropped skills</dt>
              <dd className="mt-1 font-semibold text-ink">{droppedSkills}</dd>
            </div>
          </dl>

          <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
            <div className="rounded-lg bg-sunken p-2">
              <p className="text-xs text-ink-muted">Emails</p>
              <p className="mt-1 font-semibold text-ink">{draft.redactions.emails}</p>
            </div>
            <div className="rounded-lg bg-sunken p-2">
              <p className="text-xs text-ink-muted">Phones</p>
              <p className="mt-1 font-semibold text-ink">{draft.redactions.phones}</p>
            </div>
            <div className="rounded-lg bg-sunken p-2">
              <p className="text-xs text-ink-muted">Lines</p>
              <p className="mt-1 font-semibold text-ink">{draft.redactions.lines}</p>
            </div>
            <div className="rounded-lg bg-sunken p-2">
              <p className="text-xs text-ink-muted">URLs</p>
              <p className="mt-1 font-semibold text-ink">{draft.redactions.urls}</p>
            </div>
            <div className="rounded-lg bg-sunken p-2">
              <p className="text-xs text-ink-muted">Address lines</p>
              <p className="mt-1 font-semibold text-ink">
                {draft.redactions.address_lines}
              </p>
            </div>
          </div>

          {draft.warnings.length > 0 && (
            <ul className="mt-4 list-disc space-y-1 pl-4 text-sm text-ink-muted">
              {draft.warnings.map((warning, index) => (
                <li key={index}>{warning}</li>
              ))}
            </ul>
          )}

          <div className="mt-4 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-sunken p-3 text-sm text-ink">
            {draft.draft_content}
          </div>

          <button
            type="button"
            onClick={onAddDraft}
            className="mt-4 min-h-9 rounded-lg border border-accent-ink px-4 text-sm font-medium text-accent-ink transition-colors duration-150 hover:bg-accent-soft"
          >
            Add draft to profile text
          </button>
          {addMessage && <p className="mt-2 text-sm text-err-ink">{addMessage}</p>}
        </div>
      )}
    </div>
  )
}
