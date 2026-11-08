import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { Calculator, SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { listJobs, type JobFilters as Filters } from '../api/jobs'
import { getPreferences, recalculateAll } from '../api/matching'
import { JobBadges } from '../components/jobs/JobBadges'
import { JobFilters } from '../components/jobs/JobFilters'
import { ScoreBadge } from '../components/matching/ScoreBadge'
import { timeAgo } from '../lib/format'

const PAGE_SIZE = 25

export function JobsPage() {
  const [params, setParams] = useSearchParams()
  const [notice, setNotice] = useState('')
  const filters = Object.fromEntries(params.entries()) as Filters
  const page = Number(filters.page ?? '1')

  const { data, isPending, isError, error, isPlaceholderData, refetch } = useQuery({
    queryKey: ['jobs', filters],
    queryFn: () => listJobs(filters),
    placeholderData: keepPreviousData,
  })
  const preferences = useQuery({ queryKey: ['preferences'], queryFn: getPreferences })

  const change = (next: Filters) => {
    const clean = Object.fromEntries(Object.entries(next).filter(([, value]) => value)) as Record<string, string>
    setParams(clean)
  }
  const applyPreferences = () => {
    if (!preferences.data) return
    change({
      ordering: '-match_score',
      min_match_score: String(preferences.data.minimum_match_score),
      published_within_days: String(preferences.data.publication_window_days),
      hide_ineligible: 'true',
    })
  }
  const recalc = useMutation({
    mutationFn: recalculateAll,
    onSuccess: () => {
      setNotice('Recalculating all scores in the background. The list refreshes in a few seconds.')
      setTimeout(() => { refetch(); setNotice('') }, 6000)
    },
  })

  return (
    <div className="page">
      <h1>Jobs</h1>
      <div className="toolbar">
        <button type="button" className="btn" disabled={!preferences.data} onClick={applyPreferences}>
          <SlidersHorizontal size={16} aria-hidden="true" /> Use my preferences
        </button>
        <button type="button" className="btn" disabled={recalc.isPending} onClick={() => recalc.mutate()}>
          <Calculator size={16} aria-hidden="true" /> Recalculate scores
        </button>
        <Link to="/settings" className="muted">Edit preferences</Link>
      </div>
      {notice && <p className="notice notice-warn">{notice}</p>}
      {recalc.isError && (
        <p className="notice notice-error" role="alert">
          {recalc.error.message} <Link to="/resume">Go to your resume</Link>
        </p>
      )}
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
                <div className="job-card-head">
                  <h2><Link to={`/jobs/${job.id}`}>{job.title}</Link></h2>
                  <ScoreBadge job={job} />
                </div>
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