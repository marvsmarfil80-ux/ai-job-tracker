import { useEffect, useState } from 'react'
import RunHuntCard from '../components/RunHuntCard'
import ScoreNewJobsCard from '../components/ScoreNewJobsCard'
import SourcesList from '../components/SourcesList'
import HuntHistory from '../components/HuntHistory'
import LatestRunCard from '../components/LatestRunCard'
import ActionNotices from '../components/ActionNotices'
import ScoreResultPanel from '../components/ScoreResultPanel'
import PageHeader from '../components/PageHeader'
import SkeletonBlock from '../components/SkeletonBlock'
import ErrorState from '../components/ErrorState'
import { api } from '../lib/api'
import { ApiError } from '../types'
import type {
  HuntList,
  HuntRun,
  ScoreRunResult,
  SourceInfo,
  SourceList,
} from '../types'

export default function JobHunter() {
  const [huntList, setHuntList] = useState<HuntList | null>(null)
  const [sources, setSources] = useState<SourceInfo[]>([])
  const [offset, setOffset] = useState(0)
  const [reloadKey, setReloadKey] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [runRunning, setRunRunning] = useState(false)
  const [runMessage, setRunMessage] = useState<string | null>(null)
  const [runNotice, setRunNotice] = useState<string | null>(null)
  const [newestBusy, setNewestBusy] = useState(false)
  const [newestRun, setNewestRun] = useState<HuntRun | null>(null)

  const [scoreRunning, setScoreRunning] = useState(false)
  const [scoreResult, setScoreResult] = useState<ScoreRunResult | null>(null)
  const [scoreError, setScoreError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [huntsData, sourcesData, newestData] = await Promise.all([
          api.get<HuntList>('/hunts', { limit: 10, offset }),
          api.get<SourceList>('/sources'),
          api.get<HuntList>('/hunts', { limit: 1, offset: 0 }),
        ])
        if (cancelled) return
        setHuntList(huntsData)
        setSources(sourcesData.items)
        const newest = newestData.items[0]
        setNewestBusy(
          newest !== undefined &&
            (newest.status === 'running' ||
              newest.steps.some((step) => step.status === 'running')),
        )
        setNewestRun(newest ?? null)
        setLoadError(null)
      } catch (error) {
        if (cancelled) return
        setLoadError(
          error instanceof ApiError && typeof error.detail === 'string'
            ? error.detail
            : 'Could not load Job Hunter.',
        )
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [reloadKey, offset])

  function handleRetry() {
    setLoadError(null)
    setLoading(true)
    setReloadKey((key) => key + 1)
  }

  function handlePrevious() {
    setLoading(true)
    setOffset((value) => Math.max(0, value - 10))
  }

  function handleNext() {
    if (huntList === null) return
    if (offset + huntList.items.length >= huntList.total) return
    setLoading(true)
    setOffset((value) => value + 10)
  }

  async function handleRun() {
    setRunRunning(true)
    setRunMessage(null)
    setRunNotice(null)

    try {
      const run = await api.post<HuntRun>('/hunts')
      const allSkipped =
        run.steps.length > 0 && run.steps.every((step) => step.status === 'skipped')
      setRunNotice(
        allSkipped ? 'No source was run. See the history for the reasons.' : null,
      )
      setLoading(true)
      setOffset(0)
      setReloadKey((key) => key + 1)
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setRunMessage(error.detail)
      } else if (error instanceof ApiError && error.status === 0) {
        setRunMessage(
          'The request did not finish. The hunt may still be running. Check the history in a minute.',
        )
      } else if (error instanceof ApiError && typeof error.detail === 'string') {
        setRunMessage(error.detail)
      } else {
        setRunMessage('Could not run the hunt.')
      }
      setLoading(true)
      setReloadKey((key) => key + 1)
    } finally {
      setRunRunning(false)
    }
  }

  async function handleScore(limit: number) {
    setScoreRunning(true)
    setScoreError(null)

    try {
      const data = await api.post<ScoreRunResult>('/score/run', undefined, { limit })
      setScoreResult(data)
    } catch (error) {
      if (error instanceof ApiError && typeof error.detail === 'string') {
        setScoreError(error.detail)
      } else {
        setScoreError('Could not score jobs.')
      }
    } finally {
      setScoreRunning(false)
    }
  }

  const headerProps = {
    eyebrow: 'Automation workspace',
    title: 'Job Hunter',
    description: 'Search remote job feeds, then let AI score only the new jobs.',
  }

  if (loadError !== null) {
    return (
      <div>
        <PageHeader {...headerProps} />
        <div className="rounded-card border border-line bg-surface shadow-card">
          <ErrorState message={loadError} onRetry={handleRetry} />
        </div>
      </div>
    )
  }

  if (huntList === null) {
    return (
      <div aria-busy="true">
        <PageHeader {...headerProps} />

        <div className="grid gap-6 min-[1050px]:grid-cols-[1.25fr_0.85fr]">
          {[0, 1].map((index) => (
            <div key={index} className="rounded-card border border-line bg-surface p-5 shadow-card">
              <SkeletonBlock className="h-4 w-24" />
              <SkeletonBlock className="mt-3 h-5 w-40" />
              <SkeletonBlock className="mt-4 h-16 w-full" />
              <SkeletonBlock className="mt-2 h-16 w-full" />
            </div>
          ))}
        </div>

        <div className="mt-6 rounded-card border border-line bg-surface p-5 shadow-card">
          <SkeletonBlock className="h-4 w-32" />
          <SkeletonBlock className="mt-4 h-14 w-full" />
          <SkeletonBlock className="mt-2 h-14 w-full" />
        </div>
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        {...headerProps}
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <ScoreNewJobsCard running={scoreRunning} onScore={handleScore} />
            <RunHuntCard busy={newestBusy} running={runRunning} onRun={handleRun} />
          </div>
        }
      />

      <p className="-mt-3 mb-6 text-xs text-ink-subtle">
        Run Hunt: Fetches job feeds only. No AI is used. Score New Jobs: Uses AI (Groq). Counts toward the daily limit.
      </p>

      <ActionNotices
        busy={newestBusy}
        running={runRunning}
        runMessage={runMessage}
        runNotice={runNotice}
        scoreRunning={scoreRunning}
        scoreError={scoreError}
      />

      <ScoreResultPanel result={scoreResult} />

      <div
        className={
          newestRun !== null
            ? 'grid gap-6 min-[1050px]:grid-cols-[1.25fr_0.85fr]'
            : 'grid gap-6'
        }
      >
        {newestRun !== null && <LatestRunCard run={newestRun} />}
        <HuntHistory
          huntList={huntList}
          onPrevious={handlePrevious}
          onNext={handleNext}
          loading={loading}
        />
      </div>

      <div className="mt-6">
        <SourcesList sources={sources} />
      </div>
    </div>
  )
}
