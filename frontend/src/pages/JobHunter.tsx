import RunHuntCard from '../components/RunHuntCard'
import ScoreNewJobsCard from '../components/ScoreNewJobsCard'
import SourcesList from '../components/SourcesList'
import HuntHistory from '../components/HuntHistory'
import {
  sampleHuntList,
  sampleScoreResult,
  sampleSources,
} from '../data/jobHunterSample'

export default function JobHunter() {
  const busy = sampleHuntList.items.some(
    (run) => run.status === 'running' || run.steps.some((step) => step.status === 'running'),
  )

  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Job Hunter</h1>

      <div className="mt-6 grid grid-cols-2 gap-6">
        <RunHuntCard busy={busy} />
        <ScoreNewJobsCard result={sampleScoreResult} />
      </div>

      <div className="mt-6 grid grid-cols-3 gap-6">
        <div className="col-span-1">
          <SourcesList sources={sampleSources} />
        </div>
        <div className="col-span-2">
          <HuntHistory huntList={sampleHuntList} />
        </div>
      </div>
    </div>
  )
}
