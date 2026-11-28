import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import { BriefcaseBusiness, CalendarPlus, Check, ChevronDown } from 'lucide-react'
import ChoiceMenu from './ChoiceMenu'
import type { ChoiceOption } from './ChoiceMenu'
import { TITLE_MAX, type FollowUpDraft } from '../lib/followUps'

const inputClass =
  'min-h-10 w-full rounded-lg border border-control bg-surface px-3 text-sm text-ink placeholder:text-ink-subtle transition-colors duration-150 hover:border-ink-muted disabled:cursor-not-allowed disabled:opacity-50'

const primaryButton =
  'inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-lg bg-accent-600 px-4 text-sm font-medium text-white transition-colors duration-150 hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50'

const secondaryButton =
  'min-h-9 cursor-pointer rounded-lg border border-line bg-surface px-4 text-sm font-medium text-ink transition-colors duration-150 hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50'

type FollowUpFormProps = {
  applications: ChoiceOption[]
  saving: boolean
  error: string | null
  onSave: (draft: FollowUpDraft) => Promise<boolean>
  onCancel: () => void
}

export default function FollowUpForm({ applications, saving, error, onSave, onCancel }: FollowUpFormProps) {
  const [applicationId, setApplicationId] = useState('')
  const [title, setTitle] = useState('')
  const [dueDate, setDueDate] = useState('')
  const titleId = useId()
  const dueId = useId()
  const selected = applications.find((option) => option.value === applicationId)
  const canSave = applicationId !== '' && title.trim() !== '' && !saving

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!canSave) return
    await onSave({
      application_id: Number(applicationId),
      title: title.trim(),
      due_date: dueDate === '' ? null : dueDate,
    })
  }

  return (
    <section aria-label="New follow-up" className="mb-6 rounded-card border border-line bg-surface p-6 shadow-card">
      <div className="flex items-center gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent-soft-ink">
          <CalendarPlus size={18} aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-ink">New follow-up</h2>
          <p className="text-sm text-ink-muted">Pick an application, then write the next step.</p>
        </div>
      </div>
      <form onSubmit={handleSubmit} className="mt-5 space-y-4">
        <div className="max-w-xl">
          <p className="mb-1.5 text-sm font-medium text-ink">Application</p>
          {applications.length === 0 ? (
            <p className="text-sm text-ink-muted">No applications yet. Mark a job as applied first.</p>
          ) : (
            <ChoiceMenu
              options={applications}
              value={applicationId}
              disabled={saving}
              menuLabel="Applications"
              triggerLabel={selected ? `Application: ${selected.label}` : 'Choose an application'}
              triggerClassName="flex min-h-10 w-full cursor-pointer items-center gap-2.5 rounded-lg border border-control bg-surface px-3 text-left text-sm transition-colors duration-150 hover:border-ink-muted disabled:cursor-not-allowed disabled:opacity-50"
              triggerContent={(open) => (
                <>
                  <BriefcaseBusiness size={16} aria-hidden="true" className="shrink-0 text-ink-muted" />
                  <span className={`min-w-0 flex-1 truncate ${selected ? 'text-ink' : 'text-ink-subtle'}`}>
                    {selected ? selected.label : 'Choose an application'}
                  </span>
                  <ChevronDown
                    size={16}
                    aria-hidden="true"
                    className={`shrink-0 text-ink-muted transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
                  />
                </>
              )}
              onSelect={setApplicationId}
            />
          )}
        </div>
        <div className="max-w-xl">
          <div className="mb-1.5 flex items-center justify-between gap-3">
            <label htmlFor={titleId} className="text-sm font-medium text-ink">
              Title
            </label>
            <span className="text-xs text-ink-muted">
              {title.length}/{TITLE_MAX}
            </span>
          </div>
          <input
            id={titleId}
            type="text"
            value={title}
            maxLength={TITLE_MAX}
            onChange={(event) => setTitle(event.target.value)}
            disabled={saving}
            placeholder="Send portfolio link"
            className={inputClass}
          />
        </div>
        <div className="max-w-xs">
          <label htmlFor={dueId} className="mb-1.5 block text-sm font-medium text-ink">
            Due date <span className="font-normal text-ink-muted">(optional)</span>
          </label>
          <input
            id={dueId}
            type="date"
            value={dueDate}
            onChange={(event) => setDueDate(event.target.value)}
            disabled={saving}
            className={inputClass}
          />
        </div>
        {error !== null && (
          <p role="alert" className="max-w-xl rounded-lg bg-err-soft px-4 py-3 text-sm text-err-ink">
            {error}
          </p>
        )}
        <div className="flex items-center gap-2 pt-1">
          <button type="submit" disabled={!canSave} className={primaryButton}>
            {saving ? (
              'Saving...'
            ) : (
              <>
                <Check size={16} aria-hidden="true" />
                Save
              </>
            )}
          </button>
          <button type="button" onClick={onCancel} disabled={saving} className={secondaryButton}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  )
}
