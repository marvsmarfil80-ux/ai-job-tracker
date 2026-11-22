import type { HuntRun, HuntStep } from '../types'
import { sourceLabel } from './sources'

export type Tone = 'ok' | 'warn' | 'err' | 'info' | 'idle'

export const runTones: Record<HuntRun['status'], Tone> = {
  done: 'ok',
  running: 'warn',
  error: 'err',
}

export const stepTones: Record<HuntStep['status'], Tone> = {
  done: 'ok',
  running: 'warn',
  error: 'err',
  skipped: 'idle',
}

export function statusText(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export function stepLabel(source: string): string {
  return source === 'email' ? 'Email sync' : sourceLabel(source)
}

export function formatDuration(startedAt: string, finishedAt: string | null): string | null {
  if (finishedAt === null) return null
  const start = Date.parse(startedAt)
  const end = Date.parse(finishedAt)
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return null
  const seconds = Math.round((end - start) / 1000)
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}
