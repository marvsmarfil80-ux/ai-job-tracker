import type { JobOut } from '../types'
import type { Tone } from './hunt'

const pipelineLabels: Record<string, string> = {
  new: 'New',
  filtered_out: 'Filtered out',
  scored: 'Scored',
  error: 'Error',
}

export const PAGE_SIZE = 25

export const jobGridColumns =
  'grid grid-cols-[minmax(0,36fr)_minmax(0,28fr)_minmax(0,12fr)_minmax(0,16fr)_48px] gap-4'

export function pipelineLabel(status: string): string {
  return pipelineLabels[status] ?? status
}

export function verdictTone(verdict: string | null): Tone {
  if (verdict === 'apply') return 'ok'
  if (verdict === 'maybe') return 'warn'
  if (verdict === 'skip') return 'err'
  return 'idle'
}

export function initialOf(job: JobOut): string {
  const basis = job.company?.trim() || job.title.trim()
  return basis.charAt(0).toUpperCase() || '?'
}

export function rangeText(offset: number, count: number, total: number): string {
  const start = count === 0 ? offset : offset + 1
  const end = offset + count
  return `Showing ${start}-${end} of ${total}`
}

export function workModeLabel(mode: string): string {
  const spaced = mode.replace(/_/g, ' ').trim()
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}
