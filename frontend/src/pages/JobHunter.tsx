import { useEffect, useState } from 'react'
import RunHuntCard from '../components/RunHuntCard'
import ScoreNewJobsCard from '../components/ScoreNewJobsCard'
import SourcesList from '../components/SourcesList'
import HuntHistory from '../components/HuntHistory'
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

  const [scoreRunning, setScoreRunning] = useState(false)
  const [scoreResult, setScoreResult] = useState<ScoreRunResult | null>(null)
  const [scoreError, setScoreError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [huntsData, sourcesData] = await Promise.all([
          api.get<HuntList>('/hunts', { limit: 10, offset }),
          api.get<SourceList>('/sources'),
        ])
        if (cancelled) return
        setHuntList(huntsData)
        setSources(sourcesData.items)
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

    try {
      await api.post<HuntRun>('/hunts')
      setLoading(true)
      setOffset(0)
      setReloadKey((key) => key + 1)
    } catch (error) {
      if (error instanceof ApiError && typeof error.detail === 'string') {
        setRunMessage(error.detail)
      } else {
        setRunMessage('Could not run the hunt.')
      }
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

  if (loadError !== null) {
    return (
      <div>
        <h1 className="text-2xl font-semibold text-neutral-900">Job Hunter</h1>
        <div className="mt-6 rounded-lg border border-neutral-200 bg-white">
          <ErrorState message={loadError} onRetry={handleRetry} />
        </div>
      </div>
    )
  }

  if (huntList === null) {
    return (
      <div aria-busy="true">
        <h1 className="text-2xl font-semibold text-neutral-900">Job Hunter</h1>

        <div className="mt-6 grid grid-cols-2 gap-6">
          {[0, 1].map((index) => (
            <div key={index} className="rounded-lg border border-neutral-200 bg-white p-5">
              <SkeletonBlock className="h-5 w-32" />
              <SkeletonBlock className="mt-2 h-4 w-64" />
              <SkeletonBlock className="mt-4 h-8 w-24" />
            </div>
          ))}
        </div>

        <div className="mt-6 grid grid-cols-3 gap-6">
          <div className="col-span-1 rounded-lg border border-neutral-200 bg-white p-5">
            <SkeletonBlock className="h-5 w-24" />
            <SkeletonBlock className="mt-4 h-16 w-full" />
            <SkeletonBlock className="mt-2 h-16 w-full" />
          </div>
          <div className="col-span-2 rounded-lg border border-neutral-200 bg-white p-5">
            <SkeletonBlock className="h-5 w-32" />
            {[0, 1, 2].map((index) => (
              <SkeletonBlock key={index} className="mt-4 h-20 w-full" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  const busy = huntList.items.some(
    (run) => run.status === 'running' || run.steps.some((step) => step.status === 'running'),
  )

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Job Hunter</h1>

      <div className="mt-6 grid grid-cols-2 gap-6">
        <RunHuntCard
          busy={busy}
          running={runRunning}
          message={runMessage}
          onRun={handleRun}
        />
        <ScoreNewJobsCard
          running={scoreRunning}
          result={scoreResult}
          error={scoreError}
          onScore={handleScore}
        />
      </div>

      <div className="mt-6 grid grid-cols-3 gap-6">
        <div className="col-span-1">
          <SourcesList sources={sources} />
        </div>
        <div className="col-span-2">
          <HuntHistory
            huntList={huntList}
            onPrevious={handlePrevious}
            onNext={handleNext}
            loading={loading}
          />
        </div>
      </div>
    </div>
  )
}
