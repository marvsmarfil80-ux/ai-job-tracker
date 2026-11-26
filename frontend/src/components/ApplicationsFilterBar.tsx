import { Search } from 'lucide-react'
import { FilterChip } from './JobsFilterBar'
import type { Option } from './JobsFilterBar'
import { statusOptions } from '../lib/applications'

export type ApplicationFilters = {
  search: string
  status: string
}

type ApplicationsFilterBarProps = {
  filters: ApplicationFilters
  onChange: (filters: ApplicationFilters) => void
  onClear: () => void
}

const options: Option[] = [{ value: '', label: 'All' }, ...statusOptions]

export default function ApplicationsFilterBar({ filters, onChange, onClear }: ApplicationsFilterBarProps) {
  const isDirty = filters.search !== '' || filters.status !== ''

  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-card border border-line bg-surface p-3 shadow-card">
      <div className="relative min-w-[160px] flex-1">
        <Search
          size={15}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle"
          aria-hidden="true"
        />
        <input
          type="search"
          value={filters.search}
          onChange={(event) => onChange({ ...filters, search: event.target.value })}
          placeholder="Search title or company"
          aria-label="Search applications"
          className="h-10 w-full rounded-lg bg-sunken pl-9 pr-3 text-sm text-ink placeholder:text-ink-subtle"
        />
      </div>

      <FilterChip
        label="Status"
        ariaLabel="Application status"
        value={filters.status}
        options={options}
        onChange={(value) => onChange({ ...filters, status: value })}
      />

      {isDirty && (
        <button
          type="button"
          onClick={onClear}
          className="h-10 shrink-0 whitespace-nowrap px-1 text-sm font-medium text-accent-ink hover:underline"
        >
          Clear filters
        </button>
      )}
    </div>
  )
}
