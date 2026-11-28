import { useState } from 'react'
import { Plus } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import FollowUpForm from '../components/FollowUpForm'
import FollowUpList from '../components/FollowUpList'
import type { ChoiceOption } from '../components/ChoiceMenu'
import { sampleApplications } from '../data/applicationsSample'
import { sampleFollowUpCounts, sampleFollowUps } from '../data/followUpsSample'
import { jobLabel, type FollowUpCounts, type FollowUpFilter } from '../lib/followUps'

const primaryButton =
  'inline-flex min-h-9 cursor-pointer items-center gap-2 rounded-lg bg-accent-600 px-4 text-sm font-medium text-white transition-colors duration-150 hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50'

const applicationOptions: ChoiceOption[] = sampleApplications.map((application) => ({
  value: String(application.id),
  label: jobLabel(application.job.title, application.job.company),
}))

type SummaryCardProps = {
  label: string
  value: number
  hint: string
  warn?: boolean
}

function SummaryCard({ label, value, hint, warn = false }: SummaryCardProps) {
  return (
    <div className="rounded-card border border-line bg-surface p-5 shadow-card">
      <p className="text-xs font-semibold uppercase tracking-widest text-ink-subtle">{label}</p>
      <p className={`mt-2 text-3xl font-bold tracking-tight ${warn && value > 0 ? 'text-warn-ink' : 'text-ink'}`}>
        {value}
      </p>
      <p className="mt-1 text-xs text-ink-muted">{hint}</p>
    </div>
  )
}

export default function FollowUps() {
  const [filter, setFilter] = useState<FollowUpFilter>('pending')
  const [formOpen, setFormOpen] = useState(false)
  const counts: FollowUpCounts = sampleFollowUpCounts
  const items = sampleFollowUps.filter((item) => item.status === filter)

  return (
    <div>
      <PageHeader
        eyebrow="SIMPLE TO-DO LIST"
        title="Follow-ups"
        description="Small next steps keep good applications warm."
        actions={
          <button type="button" onClick={() => setFormOpen(true)} disabled={formOpen} className={primaryButton}>
            <Plus size={16} aria-hidden="true" />
            Add follow-up
          </button>
        }
      />
      <section aria-label="Follow-up summary" className="mb-6 grid gap-4 sm:grid-cols-3">
        <SummaryCard label="Open" value={counts.open} hint="Pending follow-ups" />
        <SummaryCard label="Overdue" value={counts.overdue} hint="Due date has passed" warn />
        <SummaryCard label="Completed" value={counts.completed} hint="Marked done" />
      </section>
      {formOpen && (
        <FollowUpForm
          applications={applicationOptions}
          saving={false}
          error={null}
          onSave={() => {
            setFormOpen(false)
            return Promise.resolve(true)
          }}
          onCancel={() => setFormOpen(false)}
        />
      )}
      <FollowUpList
        items={items}
        filter={filter}
        offset={0}
        total={items.length}
        disabled={false}
        refreshing={false}
        busy={null}
        onFilterChange={setFilter}
        onToggle={() => undefined}
        onSaveEdit={() => Promise.resolve(true)}
        onDelete={() => Promise.resolve(true)}
        onAdd={() => setFormOpen(true)}
        onPrevious={() => undefined}
        onNext={() => undefined}
      />
    </div>
  )
}
