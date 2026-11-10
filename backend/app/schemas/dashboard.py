from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_applications: int
    interviews: int
    pending_follow_ups: int
    jobs_discovered: int
    recommended_jobs: int