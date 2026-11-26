import { ChevronDown, Search } from 'lucide-react'

export type JobFilters = {
  search: string
  verdict: string
  pipeline: string
  sort: string
  openedOnly: boolean
}

type JobsFilterBarProps = {
  filters: JobFilters
  onChange: (filters: JobFilters) => void
  onClear: () => void
}

type Option = {
  value: string
  label: string
}

type FilterChipProps = {
  label: string
  ariaLabel: string
  value: string
  options: Option[]
  onChange: (value: string) => void
}

const verdictOptions: Option[] = [
  { value: '', label: 'All' },
  { value: 'apply', label: 'Apply' },
  { value: 'maybe', label: 'Maybe' },
  { value: 'skip', label: 'Skip' },
]

const pipelineOptions: Option[] = [
  { value: '', label: 'All' },
  { value: 'new', label: 'New' },
  { value: 'filtered_out', label: 'Filtered out' },
  { value: 'scored', label: 'Scored' },
  { value: 'error', label: 'Error' },
]

const sortOptions: Option[] = [
  { value: '', label: 'Default' },
  { value: 'score_desc', label: 'Score high to low' },
]

function FilterChip({ label, ariaLabel, value, options, onChange }: FilterChipProps) {
  const selected = options.find((option) => option.value === value) ?? options[0]

  return (
    <label className="relative flex h-10 shrink-0 cursor-pointer items-center gap-1 rounded-lg bg-sunken px-2 has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-focus">
      <span className="whitespace-nowrap text-xs font-medium text-ink-subtle">{label}</span>
      <span className="flex items-center gap-1 whitespace-nowrap text-sm font-semibold text-ink">
        {selected.label}
        <ChevronDown size={12} className="text-ink-subtle" aria-hidden="true" />
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={ariaLabel}
        className="absolute inset-0 h-full w-full cursor-pointer appearance-none opacity-0"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export default function JobsFilterBar({ filters, onChange, onClear }: JobsFilterBarProps) {
  const isDirty =
    filters.search !== '' ||
    filters.verdict !== '' ||
    filters.pipeline !== '' ||
    filters.sort !== '' ||
    filters.openedOnly

  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-card border border-line bg-surface p-3 shadow-card min-[1280px]:flex-nowrap min-[1280px]:overflow-x-auto">
      <div className="relative min-w-[120px] flex-1">
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
          aria-label="Search jobs"
          className="h-10 w-full rounded-lg bg-sunken pl-9 pr-3 text-sm text-ink placeholder:text-ink-subtle"
        />
      </div>

      <FilterChip
        label="Verdict"
        ariaLabel="Verdict"
        value={filters.verdict}
        options={verdictOptions}
        onChange={(value) => onChange({ ...filters, verdict: value })}
      />

      <FilterChip
        label="Pipeline"
        ariaLabel="Pipeline status"
        value={filters.pipeline}
        options={pipelineOptions}
        onChange={(value) => onChange({ ...filters, pipeline: value })}
      />

      <FilterChip
        label="Sort"
        ariaLabel="Sort"
        value={filters.sort}
        options={sortOptions}
        onChange={(value) => onChange({ ...filters, sort: value })}
      />

      <button
        type="button"
        aria-pressed={filters.openedOnly}
        onClick={() => onChange({ ...filters, openedOnly: !filters.openedOnly })}
        className={`h-10 shrink-0 whitespace-nowrap rounded-lg px-2.5 text-sm font-medium ${
          filters.openedOnly
            ? 'bg-accent-soft text-accent-soft-ink'
            : 'bg-sunken text-ink-muted hover:text-ink'
        }`}
      >
        Opened, not applied
      </button>

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
