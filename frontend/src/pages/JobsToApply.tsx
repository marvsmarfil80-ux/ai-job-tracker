import { useState } from 'react'
import type { JobOut } from '../types'
import PageHeader from '../components/PageHeader'
import JobsFilterBar from '../components/JobsFilterBar'
import type { JobFilters } from '../components/JobsFilterBar'
import JobsTable from '../components/JobsTable'
import type { JobsTab } from '../components/JobsTable'
import { sampleJobs } from '../data/jobsSample'
import { PAGE_SIZE } from '../lib/jobs'

const initialFilters: JobFilters = {
  search: '',
  verdict: '',
  pipeline: '',
  sort: '',
  openedOnly: false,
}

export default function JobsToApply() {
  const [tab, setTab] = useState<JobsTab>('active')
  const [jobs, setJobs] = useState<JobOut[]>(sampleJobs)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [offset, setOffset] = useState(0)
  const [filters, setFilters] = useState<JobFilters>(initialFilters)

  const activeCount = jobs.filter((job) => job.dismissed_at === null).length
  const dismissedCount = jobs.length - activeCount
  const tabJobs = jobs.filter((job) =>
    tab === 'dismissed' ? job.dismissed_at !== null : job.dismissed_at === null,
  )
  const pageJobs = tabJobs.slice(offset, offset + PAGE_SIZE)

  function handleTabChange(next: JobsTab) {
    setTab(next)
    setOffset(0)
    setExpandedId(null)
  }

  function handleToggle(id: number) {
    setExpandedId((current) => (current === id ? null : id))
  }

  function handleDismiss(id: number) {
    setJobs((current) =>
      current.map((job) =>
        job.id === id ? { ...job, dismissed_at: new Date().toISOString() } : job,
      ),
    )
    setExpandedId(null)
  }

  function handleRestore(id: number) {
    setJobs((current) =>
      current.map((job) => (job.id === id ? { ...job, dismissed_at: null } : job)),
    )
    setExpandedId(null)
  }

  function handleApplied(id: number) {
    setJobs((current) =>
      current.map((job) => (job.id === id ? { ...job, application_id: -1 } : job)),
    )
  }

  function handlePrevious() {
    setOffset((current) => Math.max(0, current - PAGE_SIZE))
  }

  function handleNext() {
    setOffset((current) =>
      current + PAGE_SIZE >= tabJobs.length ? current : current + PAGE_SIZE,
    )
  }

  return (
    <div>
      <PageHeader
        eyebrow="REVIEW QUEUE"
        title="Jobs to Apply"
        description="The AI suggests. You decide what happens next."
      />

      <JobsFilterBar
        filters={filters}
        onChange={setFilters}
        onClear={() => setFilters(initialFilters)}
      />

      <div className="mt-6">
        <JobsTable
          tab={tab}
          onTabChange={handleTabChange}
          jobs={pageJobs}
          offset={offset}
          total={tabJobs.length}
          activeCount={activeCount}
          dismissedCount={dismissedCount}
          expandedId={expandedId}
          onToggle={handleToggle}
          onPrevious={handlePrevious}
          onNext={handleNext}
          onDismiss={handleDismiss}
          onRestore={handleRestore}
          onApplied={handleApplied}
        />
      </div>
    </div>
  )
}
