import { LEVEL_LABEL, TYPE_LABEL, WORK_LABEL, eligibilityLabel, type JobSummary } from '../../api/jobs'

export function JobBadges({ job }: { job: JobSummary }) {
  const eligibility = eligibilityLabel(job)
  return (
    <>
      <ul className="chips">
        <li className={`chip chip-${job.work_arrangement}`}>{WORK_LABEL[job.work_arrangement]}</li>
        {job.experience_level !== 'unknown' && <li className="chip">{LEVEL_LABEL[job.experience_level]}</li>}
        {job.employment_type !== 'unknown' && <li className="chip">{TYPE_LABEL[job.employment_type]}</li>}
        {job.location_text && <li className="chip">{job.location_text}</li>}
      </ul>
      {eligibility && (
        <p className={job.remote_eligibility === 'unknown' ? 'muted eligibility eligibility-unknown' : 'muted eligibility'}>
          {eligibility}
        </p>
      )}
    </>
  )
}