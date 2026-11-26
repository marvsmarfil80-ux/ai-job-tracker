import { useState } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import ApplicationsFilterBar from '../components/ApplicationsFilterBar'
import type { ApplicationFilters } from '../components/ApplicationsFilterBar'
import ApplicationList from '../components/ApplicationList'
import ApplicationDetailPanel from '../components/ApplicationDetailPanel'
import type { ApplicationChanges, ApplicationDetail } from '../lib/applications'
import { APPLICATION_PAGE_SIZE } from '../lib/applications'
import { sampleApplications } from '../data/applicationsSample'

const initialFilters: ApplicationFilters = { search: '', status: '' }

export default function Applications() {
  const [filters, setFilters] = useState<ApplicationFilters>(initialFilters)
  const [showFilters, setShowFilters] = useState(false)
  const [items, setItems] = useState<ApplicationDetail[]>(sampleApplications)
  const [offset, setOffset] = useState(0)
  const [selectedId, setSelectedId] = useState<number | null>(sampleApplications[0]?.id ?? null)
  const [version, setVersion] = useState(0)

  const query = filters.search.trim().toLowerCase()
  const filtered = items.filter(
    (item) =>
      (filters.status === '' || item.status === filters.status) &&
      (query === '' ||
        item.job.title.toLowerCase().includes(query) ||
        (item.job.company ?? '').toLowerCase().includes(query)),
  )
  const pageItems = filtered.slice(offset, offset + APPLICATION_PAGE_SIZE)
  const selected = items.find((item) => item.id === selectedId) ?? null
  const filtersActive = query !== '' || filters.status !== ''
  const activeFilterCount = (query !== '' ? 1 : 0) + (filters.status !== '' ? 1 : 0)

  function handleFiltersChange(next: ApplicationFilters) {
    setFilters(next)
    setOffset(0)
  }

  function handleClear() {
    setFilters(initialFilters)
    setOffset(0)
  }

  function handlePrevious() {
    setOffset((current) => Math.max(0, current - APPLICATION_PAGE_SIZE))
  }

  function handleNext() {
    setOffset((current) =>
      current + APPLICATION_PAGE_SIZE >= filtered.length ? current : current + APPLICATION_PAGE_SIZE,
    )
  }

  function handleSave(changes: ApplicationChanges): Promise<boolean> {
    if (selected === null) return Promise.resolve(false)
    const newStatus = changes.status
    const nextId = Math.max(0, ...items.flatMap((item) => item.events.map((event) => event.id))) + 1
    const events =
      newStatus !== undefined && newStatus !== selected.status
        ? [
            ...selected.events,
            {
              id: nextId,
              from_status: selected.status,
              to_status: newStatus,
              changed_at: new Date().toISOString(),
            },
          ]
        : selected.events
    const updated: ApplicationDetail = {
      ...selected,
      status: newStatus ?? selected.status,
      notes: changes.notes !== undefined ? changes.notes : selected.notes,
      events,
    }
    setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)))
    setVersion((value) => value + 1)
    return Promise.resolve(true)
  }

  function handleDelete(): Promise<boolean> {
    if (selected === null) return Promise.resolve(false)
    const remaining = items.filter((item) => item.id !== selected.id)
    setItems(remaining)
    setSelectedId(remaining[0]?.id ?? null)
    return Promise.resolve(true)
  }

  return (
    <div>
      <PageHeader
        eyebrow="PIPELINE"
        title="Applications"
        description="Track where each application stands and keep notes in one place."
        actions={
          <button
            type="button"
            onClick={() => setShowFilters((value) => !value)}
            aria-expanded={showFilters}
            aria-controls="application-filters"
            className="inline-flex h-10 items-center gap-2 whitespace-nowrap rounded-lg border border-control bg-surface px-3.5 text-sm font-medium text-ink hover:bg-sunken"
          >
            <SlidersHorizontal size={15} aria-hidden="true" />
            Filter applications
            {activeFilterCount > 0 && (
              <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-accent-600 px-1.5 text-xs font-semibold text-white">
                {activeFilterCount}
              </span>
            )}
          </button>
        }
      />

      {showFilters && (
        <div id="application-filters" className="mb-6">
          <ApplicationsFilterBar filters={filters} onChange={handleFiltersChange} onClear={handleClear} />
        </div>
      )}

      <div className="grid items-start gap-6 min-[1050px]:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <ApplicationList
          items={pageItems}
          offset={offset}
          total={filtered.length}
          selectedId={selectedId}
          disabled={false}
          filtersActive={filtersActive}
          onSelect={setSelectedId}
          onPrevious={handlePrevious}
          onNext={handleNext}
          onClearFilters={handleClear}
        />
        <div className="min-[1050px]:sticky min-[1050px]:top-6">
          <ApplicationDetailPanel
            key={`${selectedId ?? 'none'}-${version}`}
            detail={selected}
            busy={null}
            disabled={false}
            error={null}
            onSave={handleSave}
            onDelete={handleDelete}
          />
        </div>
      </div>
    </div>
  )
}
