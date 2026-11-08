import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { listJobs, type JobFilters as Filters } from '../api/jobs'
import { JobBadges } from '../components/jobs/JobBadges'
import { JobFilters } from '../components/jobs/JobFilters'
import { timeAgo } from '../lib/format'

const PAGE_SIZE = 25

export function JobsPage() {
  const [params, setParams] = useSearchParams()
  const filters = Object.fromEntries(params.entries()) as Filters
  const page = Number(filters.page ?? '1')

  const { data, isPending, isError, error, isPlaceholderData } = useQuery({
    queryKey: ['jobs', filters],
    queryFn: () => listJobs(filters),
    placeholderData: keepPreviousData,
  })

  const change = (next: Filters) => {
    const clean = Object.fromEntries(Object.entries(next).filter(([, value]) => value)) as Record<string, string>
    setParams(clean)
  }

  return (
    <div className="page">
      <h1>Jobs</h1>
      <JobFilters filters={filters} onChange={change} />
      {isPending && <p className="muted">Loading jobs…</p>}
      {isError && <p className="notice notice-error" role="alert">{error.message}</p>}
      {data && data.count === 0 && (
        <p className="muted">
          No jobs match. {Object.keys(filters).length ? 'Try clearing a filter, or ' : 'Run '}
          <Link to="/discovery">run a discovery</Link> to fetch listings.
        </p>
      )}
      {data && data.count > 0 && (
        <>
          <p className="muted">{data.count} job{data.count === 1 ? '' : 's'}</p>
          <ul className="job-list" aria-busy={isPlaceholderData}>
            {data.results.map((job) => (
              <li key={job.id} className="job-card">
                <h2><Link to={`/jobs/${job.id}`}>{job.title}</Link></h2>
                <p className="job-company">{job.company_name}</p>
                <JobBadges job={job} />
                <p className="muted job-meta">
                  {timeAgo(job.published_at)} · Listed by {job.sources.map((s) => s.source_name).join(', ')}
                  {job.last_verified_at ? '' : ' · Not verified yet'}
                </p>
              </li>
            ))}
          </ul>
          <nav className="pager" aria-label="Pagination">
            <button type="button" className="btn" disabled={!data.previous}
              onClick={() => change({ ...filters, page: String(page - 1) })}>Previous</button>
            <span className="muted">Page {page} of {Math.max(1, Math.ceil(data.count / PAGE_SIZE))}</span>
            <button type="button" className="btn" disabled={!data.next}
              onClick={() => change({ ...filters, page: String(page + 1) })}>Next</button>
          </nav>
        </>
      )}
    </div>
  )
}