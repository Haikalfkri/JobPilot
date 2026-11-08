import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getJob, verifyJob } from '../api/jobs'
import { JobBadges } from '../components/jobs/JobBadges'
import { MatchPanel } from '../components/matching/MatchPanel'
import { formatDate, formatDateTime, safeHref } from '../lib/format'

const STATUS_TEXT = {
  active: 'Listed by its source',
  closed: 'The source page is gone',
  expired: 'Expired',
  unknown: 'Availability unknown',
} as const

export function JobDetailPage() {
  const { jobId = '' } = useParams()
  const queryClient = useQueryClient()
  const [checking, setChecking] = useState(false)

  // Poll for a short while after queuing a verification, then stop.
  useEffect(() => {
    if (!checking) return
    const timer = setTimeout(() => setChecking(false), 20_000)
    return () => clearTimeout(timer)
  }, [checking])

  const { data: job, isPending, isError, error } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => getJob(jobId),
    refetchInterval: checking ? 2000 : false,
  })
  const verify = useMutation({
    mutationFn: () => verifyJob(jobId),
    onSuccess: () => {
      setChecking(true)
      queryClient.invalidateQueries({ queryKey: ['job', jobId] })
    },
  })

  if (isPending) return <p className="muted">Loading job…</p>
  if (isError) return <p className="notice notice-error" role="alert">{error.message}</p>

  const salary = job.salary_min || job.salary_max
    ? `${job.salary_min ?? '?'} to ${job.salary_max ?? '?'} ${job.salary_currency ?? ''} per year`
    : null

  return (
    <div className="page">
      <Link to="/jobs" className="back-link"><ArrowLeft size={16} aria-hidden="true" /> All jobs</Link>
      <header>
        <h1>{job.title}</h1>
        <p className="job-company">{job.company_name}</p>
        <JobBadges job={job} />
        {salary && <p className="muted">Salary stated by the source: {salary}</p>}
      </header>

      <MatchPanel jobId={jobId} />
      
      <section className="panel">
        <h2>Availability</h2>
        <p>{STATUS_TEXT[job.status]}.{' '}
          {job.last_verified_at ? `Last verified ${formatDateTime(job.last_verified_at)}.` : 'Not verified by JobPilot yet.'}
        </p>
        <button type="button" className="btn" disabled={verify.isPending || checking}
          onClick={() => verify.mutate()}>
          <RefreshCw size={16} aria-hidden="true" /> Check if still open
        </button>
        {verify.isError && <p className="notice notice-error" role="alert">{verify.error.message}</p>}
        {checking && <p className="muted">Checking… this page updates on its own.</p>}
      </section>

      <section>
        <h2>Sources</h2>
        <ul className="source-links">
          {job.listings.map((listing) => (
            <li key={listing.original_url}>
              <a href={safeHref(listing.original_url)} target="_blank" rel="noopener noreferrer">
                {listing.source_name} <ExternalLink size={14} aria-hidden="true" />
              </a>
              <span className="muted">
                {' '}first seen {formatDate(listing.first_seen_at)}, last seen {formatDate(listing.last_seen_at)}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Description</h2>
        {job.description ? <div className="job-description">{job.description}</div>
          : <p className="muted">The source did not provide a description.</p>}
      </section>
    </div>
  )
}