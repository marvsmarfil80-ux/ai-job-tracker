import { CalendarCheck, Clock, FileText, Search } from 'lucide-react'
import { Link } from 'react-router-dom'
import StatCard from '../components/StatCard'
import RecommendedJobRow from '../components/RecommendedJobRow'
import { sampleRecommended, sampleSummary } from '../data/dashboardSample'

export default function Dashboard() {
  return (
    <div>
      <h1 className="text-2xl font-semibold text-neutral-900">Dashboard</h1>

      <div className="mt-6 grid grid-cols-4 gap-4">
        <StatCard
          label="Total Applications"
          value={sampleSummary.total_applications}
          icon={FileText}
        />
        <StatCard label="Interviews" value={sampleSummary.interviews} icon={CalendarCheck} />
        <StatCard
          label="Pending Follow-ups"
          value={sampleSummary.pending_follow_ups}
          icon={Clock}
        />
        <StatCard
          label="Jobs Discovered"
          value={sampleSummary.jobs_discovered}
          icon={Search}
        />
      </div>

      <div className="mt-6 rounded-lg border border-neutral-200 bg-white p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-baseline gap-2">
            <h2 className="font-semibold text-neutral-900">AI Recommended Jobs</h2>
            <span className="text-sm text-neutral-500">
              {sampleSummary.recommended_jobs} total
            </span>
          </div>
          <Link
            to="/jobs"
            className="text-sm font-medium text-accent-600 hover:text-accent-700"
          >
            View all
          </Link>
        </div>

        <div className="mt-2 divide-y divide-neutral-200">
          {sampleRecommended.map((job) => (
            <RecommendedJobRow key={job.id} job={job} />
          ))}
        </div>
      </div>
    </div>
  )
}
