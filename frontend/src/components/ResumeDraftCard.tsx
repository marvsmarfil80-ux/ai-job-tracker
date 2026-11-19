import { useState } from 'react'
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
    <div className="rounded-lg border border-neutral-200 bg-white p-5">
      <h2 className="font-semibold text-neutral-900">Resume draft</h2>
      <p className="mt-1 text-sm text-neutral-500">
        Your PDF text is sent to Groq, a third party, after emails, phone numbers and contact
        lines are removed. Names, employers, schools and job titles are not removed.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <input
          aria-label="Resume PDF"
          type="file"
          accept="application/pdf,.pdf"
          onChange={handleFileChange}
          disabled={busy}
          className="block text-sm text-neutral-600 file:mr-3 file:rounded-md file:border-0 file:bg-neutral-100 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-neutral-700 hover:file:bg-neutral-200"
        />
        <button
          type="button"
          onClick={() => {
            if (selectedFile) onCreate(selectedFile)
          }}
          disabled={!selectedFile || busy}
          className="rounded-md bg-accent-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
        >
          Create draft
        </button>
      </div>

      {busy && (
        <p className="mt-2 text-sm text-neutral-600">
          Reading your PDF and asking Groq. This can take a while.
        </p>
      )}
      {error && (
        <>
          <p className="mt-2 text-sm text-red-600">{error.detail}</p>
          {error.status === 429 && error.detail === 'Daily resume draft limit reached.' && (
            <p className="mt-1 text-sm text-neutral-600">
              Resume drafts are limited to 5 per day (UTC), shared with job scoring.
            </p>
          )}
        </>
      )}
      {fileError && <p className="mt-2 text-sm text-red-600">{fileError}</p>}
      {selectedFile && (
        <p className="mt-2 text-sm text-neutral-600">
          {selectedFile.name} ({formatFileSize(selectedFile.size)})
        </p>
      )}

      {draft !== null && (
        <div className="mt-5 border-t border-neutral-200 pt-5">
          <div className="flex flex-wrap gap-1.5">
            {draft.skills.map((skill, index) => (
              <span
                key={`${skill}-${index}`}
                className="rounded-md bg-accent-50 px-2.5 py-1 text-sm font-medium text-accent-700"
              >
                {skill}
              </span>
            ))}
          </div>

          <dl className="mt-4 grid grid-cols-4 gap-3 text-sm">
            <div>
              <dt className="text-neutral-500">Pages</dt>
              <dd className="mt-1 font-semibold text-neutral-900">{draft.pages}</dd>
            </div>
            <div>
              <dt className="text-neutral-500">Extracted chars</dt>
              <dd className="mt-1 font-semibold text-neutral-900">{draft.extracted_chars}</dd>
            </div>
            <div>
              <dt className="text-neutral-500">Truncated</dt>
              <dd className="mt-1 font-semibold text-neutral-900">
                {draft.truncated ? 'Yes' : 'No'}
              </dd>
            </div>
            <div>
              <dt className="text-neutral-500">Dropped skills</dt>
              <dd className="mt-1 font-semibold text-neutral-900">{droppedSkills}</dd>
            </div>
          </dl>

          <div className="mt-4 grid grid-cols-5 gap-2 text-sm">
            <div className="rounded-md bg-neutral-50 p-2">
              <p className="text-xs text-neutral-500">Emails</p>
              <p className="mt-1 font-semibold text-neutral-900">{draft.redactions.emails}</p>
            </div>
            <div className="rounded-md bg-neutral-50 p-2">
              <p className="text-xs text-neutral-500">Phones</p>
              <p className="mt-1 font-semibold text-neutral-900">{draft.redactions.phones}</p>
            </div>
            <div className="rounded-md bg-neutral-50 p-2">
              <p className="text-xs text-neutral-500">Lines</p>
              <p className="mt-1 font-semibold text-neutral-900">{draft.redactions.lines}</p>
            </div>
            <div className="rounded-md bg-neutral-50 p-2">
              <p className="text-xs text-neutral-500">URLs</p>
              <p className="mt-1 font-semibold text-neutral-900">{draft.redactions.urls}</p>
            </div>
            <div className="rounded-md bg-neutral-50 p-2">
              <p className="text-xs text-neutral-500">Address lines</p>
              <p className="mt-1 font-semibold text-neutral-900">
                {draft.redactions.address_lines}
              </p>
            </div>
          </div>

          {draft.warnings.length > 0 && (
            <ul className="mt-4 list-disc space-y-1 pl-4 text-sm text-neutral-600">
              {draft.warnings.map((warning, index) => (
                <li key={index}>{warning}</li>
              ))}
            </ul>
          )}

          <div className="mt-4 max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-neutral-50 p-3 text-sm text-neutral-700">
            {draft.draft_content}
          </div>

          <button
            type="button"
            onClick={onAddDraft}
            className="mt-4 rounded-md border border-accent-600 px-3 py-1.5 text-sm font-medium text-accent-700 hover:bg-accent-50"
          >
            Add draft to profile text
          </button>
          {addMessage && <p className="mt-2 text-sm text-red-600">{addMessage}</p>}
        </div>
      )}
    </div>
  )
}
