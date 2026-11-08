import type { JobSummary } from '../../api/jobs'

export function ScoreBadge({ job }: { job: Pick<JobSummary, 'match_score' | 'match_eligibility'> }) {
  if (job.match_score === null) return <span className="score score-none">Not scored</span>
  const band = job.match_score >= 75 ? 'high' : job.match_score >= 50 ? 'mid' : 'low'
  return (
    <span className="score-group">
      <span className={`score score-${band}`} title="Estimated fit with your confirmed resume facts">
        {Math.round(job.match_score)}% match
      </span>
      {job.match_eligibility === 'ineligible' && <span className="score score-ineligible">Not open to you</span>}
      {job.match_eligibility === 'uncertain' && <span className="score score-uncertain">Eligibility unclear</span>}
    </span>
  )
}