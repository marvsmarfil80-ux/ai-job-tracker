import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import { Check, Pencil, Plus, Trash2 } from 'lucide-react'
import EmptyState from './EmptyState'
import SkeletonBlock from './SkeletonBlock'
import StatusBadge from './StatusBadge'
import { formatDate } from '../lib/time'
import {
  TITLE_MAX,
  applicationLabel,
  formatDueDate,
  type FollowUpBusy,
  type FollowUpChanges,
  type FollowUpDetail,
  type FollowUpFilter,
} from '../lib/followUps'

const inputClass =
  'min-h-9 w-full rounded-lg border border-control bg-surface px-3 text-sm text-ink disabled:cursor-not-allowed disabled:opacity-50'

const primaryButton =
  'inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-lg bg-accent-600 px-4 text-sm font-medium text-white transition-colors duration-150 hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50'

const secondaryButton =
  'inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-lg border border-line bg-surface px-3 text-sm font-medium text-ink transition-colors duration-150 hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50'

const dangerButton =
  'min-h-9 cursor-pointer rounded-lg border border-line bg-surface px-3 text-sm font-medium text-err-ink transition-colors duration-150 hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50'

const iconButton =
  'inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg text-ink-subtle transition-colors duration-150 hover:bg-sunken disabled:cursor-not-allowed disabled:opacity-50'

const filterOptions: { value: FollowUpFilter; label: string }[] = [
  { value: 'pending', label: 'Pending' },
  { value: 'completed', label: 'Completed' },
]

type ListHeaderProps = {
  filter: FollowUpFilter
  disabled: boolean
  onFilterChange: (next: FollowUpFilter) => void
}

function ListHeader({ filter, disabled, onFilterChange }: ListHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-6 py-4">
      <h2 className="text-sm font-semibold text-ink">
        {filter === 'pending' ? 'Pending follow-ups' : 'Completed follow-ups'}
      </h2>
      <div role="group" aria-label="Show follow-ups" className="inline-flex items-center gap-1 rounded-lg bg-sunken p-1">
        {filterOptions.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={filter === option.value}
            onClick={() => onFilterChange(option.value)}
            disabled={disabled}
            className={`min-h-8 cursor-pointer rounded-md px-3 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed ${
              filter === option.value ? 'bg-surface text-accent-ink shadow-sm' : 'text-ink-muted hover:text-ink'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}

type EditRowProps = {
  item: FollowUpDetail
  saving: boolean
  onSave: (changes: FollowUpChanges) => void
  onCancel: () => void
}

function EditRow({ item, saving, onSave, onCancel }: EditRowProps) {
  const [title, setTitle] = useState(item.title)
  const [dueDate, setDueDate] = useState(item.due_date ?? '')
  const titleId = useId()
  const dueId = useId()
  const trimmed = title.trim()

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (trimmed === '' || saving) return
    const changes: FollowUpChanges = {}
    if (trimmed !== item.title) changes.title = trimmed
    const nextDue = dueDate === '' ? null : dueDate
    if (nextDue !== item.due_date) changes.due_date = nextDue
    onSave(changes)
  }

  return (
    <form onSubmit={handleSubmit} className="flex min-w-0 flex-1 flex-wrap items-end gap-3">
      <div className="min-w-0 flex-1 basis-64">
        <div className="mb-1.5 flex items-center justify-between gap-3">
          <label htmlFor={titleId} className="text-xs font-medium text-ink-muted">
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
          className={inputClass}
        />
      </div>
      <div className="w-44">
        <label htmlFor={dueId} className="mb-1.5 block text-xs font-medium text-ink-muted">
          Due date
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
      <div className="flex items-center gap-2">
        <button type="submit" disabled={trimmed === '' || saving} className={primaryButton}>
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button type="button" onClick={onCancel} disabled={saving} className={secondaryButton}>
          Cancel
        </button>
      </div>
    </form>
  )
}

export function FollowUpListSkeleton() {
  return (
    <section aria-hidden="true" className="overflow-hidden rounded-card border border-line bg-surface">
      <div className="flex items-center justify-between gap-3 border-b border-line px-6 py-4">
        <SkeletonBlock className="h-4 w-36" />
        <SkeletonBlock className="h-9 w-44" />
      </div>
      <ul>
        {[0, 1, 2].map((key) => (
          <li key={key} className="flex items-center gap-4 border-b border-line px-6 py-4 last:border-b-0">
            <SkeletonBlock className="h-8 w-8 shrink-0" />
            <div className="min-w-0 flex-1 space-y-2">
              <SkeletonBlock className="h-4 w-48" />
              <SkeletonBlock className="h-3 w-64" />
            </div>
            <SkeletonBlock className="h-4 w-20 shrink-0" />
          </li>
        ))}
      </ul>
    </section>
  )
}

type FollowUpListProps = {
  items: FollowUpDetail[]
  filter: FollowUpFilter
  offset: number
  total: number
  disabled: boolean
  refreshing: boolean
  busy: FollowUpBusy
  onFilterChange: (next: FollowUpFilter) => void
  onToggle: (item: FollowUpDetail) => void
  onSaveEdit: (id: number, changes: FollowUpChanges) => Promise<boolean>
  onDelete: (id: number) => Promise<boolean>
  onAdd: () => void
  onPrevious: () => void
  onNext: () => void
}

export default function FollowUpList({
  items,
  filter,
  offset,
  total,
  disabled,
  refreshing,
  busy,
  onFilterChange,
  onToggle,
  onSaveEdit,
  onDelete,
  onAdd,
  onPrevious,
  onNext,
}: FollowUpListProps) {
  const [editingId, setEditingId] = useState<number | null>(null)
  const [confirmId, setConfirmId] = useState<number | null>(null)

  async function handleSaveEdit(id: number, changes: FollowUpChanges) {
    if (Object.keys(changes).length === 0) {
      setEditingId(null)
      return
    }
    const saved = await onSaveEdit(id, changes)
    if (saved) setEditingId(null)
  }

  async function handleDelete(id: number) {
    const deleted = await onDelete(id)
    if (deleted) setConfirmId(null)
  }

  function startEdit(id: number) {
    setConfirmId(null)
    setEditingId(id)
  }

  function startDelete(id: number) {
    setEditingId(null)
    setConfirmId(id)
  }

  const sectionClass = `overflow-hidden rounded-card border border-line bg-surface transition-opacity duration-150 ${
    refreshing ? 'opacity-60' : ''
  }`

  if (total === 0) {
    return (
      <section aria-label="Follow-ups list" aria-busy={refreshing} className={sectionClass}>
        <ListHeader filter={filter} disabled={disabled} onFilterChange={onFilterChange} />
        {filter === 'pending' ? (
          <EmptyState
            title="No pending follow-ups."
            hint="Add a follow-up to remember your next step."
            action={
              <button type="button" onClick={onAdd} disabled={disabled} className={secondaryButton}>
                <Plus size={16} aria-hidden="true" />
                Add follow-up
              </button>
            }
          />
        ) : (
          <EmptyState title="No completed follow-ups." hint="Follow-ups you mark as done appear here." />
        )}
      </section>
    )
  }

  const start = offset + 1
  const end = offset + items.length

  return (
    <section aria-label="Follow-ups list" aria-busy={refreshing} className={sectionClass}>
      <ListHeader filter={filter} disabled={disabled} onFilterChange={onFilterChange} />
      <ul>
        {items.map((item) => {
          const done = item.status === 'completed'
          const editing = editingId === item.id
          const confirming = confirmId === item.id
          const toggling = busy !== null && busy.id === item.id && busy.kind === 'toggle'
          const saving = busy !== null && busy.id === item.id && busy.kind === 'edit'
          const deleting = busy !== null && busy.id === item.id && busy.kind === 'delete'
          return (
            <li key={item.id} className="border-b border-line px-6 py-4 last:border-b-0">
              <div className="flex items-center gap-4">
                <button
                  type="button"
                  onClick={() => onToggle(item)}
                  disabled={disabled || editing}
                  aria-label={toggling ? 'Saving...' : done ? `Reopen: ${item.title}` : `Mark done: ${item.title}`}
                  className={`flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-full border transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${
                    done
                      ? 'border-transparent bg-ok-soft text-ok-ink'
                      : 'border-control text-ink-subtle hover:border-accent-600 hover:text-accent-ink'
                  }`}
                >
                  <Check size={16} aria-hidden="true" />
                </button>
                {editing ? (
                  <EditRow
                    item={item}
                    saving={saving}
                    onSave={(changes) => handleSaveEdit(item.id, changes)}
                    onCancel={() => setEditingId(null)}
                  />
                ) : (
                  <>
                    <div className="min-w-0 flex-1">
                      <p className={`break-words text-sm font-semibold ${done ? 'text-ink-muted' : 'text-ink'}`}>
                        {item.title}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-ink-muted">{applicationLabel(item.application)}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {done ? (
                        <span className="text-xs text-ink-muted">Done {formatDate(item.completed_at)}</span>
                      ) : (
                        <>
                          <span
                            className={`text-xs ${item.is_overdue ? 'font-medium text-warn-ink' : 'text-ink-muted'}`}
                          >
                            {formatDueDate(item.due_date)}
                          </span>
                          {item.is_overdue && <StatusBadge tone="warn">Overdue</StatusBadge>}
                        </>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <button
                        type="button"
                        onClick={() => startEdit(item.id)}
                        disabled={disabled}
                        aria-label={`Edit: ${item.title}`}
                        className={`${iconButton} hover:text-ink`}
                      >
                        <Pencil size={16} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        onClick={() => startDelete(item.id)}
                        disabled={disabled}
                        aria-label={`Delete: ${item.title}`}
                        className={`${iconButton} hover:text-err-ink`}
                      >
                        <Trash2 size={16} aria-hidden="true" />
                      </button>
                    </div>
                  </>
                )}
              </div>
              {confirming && (
                <div
                  role="group"
                  aria-label="Confirm delete"
                  className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg bg-err-soft px-4 py-3 sm:ml-12"
                >
                  <p className="text-sm text-err-ink">Delete this follow-up? This cannot be undone.</p>
                  <div className="flex items-center gap-2">
                    <button type="button" onClick={() => handleDelete(item.id)} disabled={disabled} className={dangerButton}>
                      {deleting ? 'Deleting...' : 'Delete'}
                    </button>
                    <button type="button" onClick={() => setConfirmId(null)} disabled={deleting} className={secondaryButton}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </li>
          )
        })}
      </ul>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-6 py-4">
        <p className="text-sm text-ink-muted">
          Showing {start}-{end} of {total}
        </p>
        <div className="flex items-center gap-2">
          <button type="button" onClick={onPrevious} disabled={disabled || offset === 0} className={secondaryButton}>
            Previous
          </button>
          <button type="button" onClick={onNext} disabled={disabled || end >= total} className={secondaryButton}>
            Next
          </button>
        </div>
      </div>
    </section>
  )
}
