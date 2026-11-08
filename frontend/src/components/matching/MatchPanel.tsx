import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Calculator } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  analyzeJob, COMPONENT_KEYS, COMPONENT_LABEL, ELIGIBILITY_TEXT, getMatchForJob, type Match,
} from '../../api/matching'

function ComponentRow({ match, name }: { match: Match; name: (typeof COMPONENT_KEYS)[number] }) {
  const score = match.components[name]
  const info = match.details?.components[name]
  const weights = match.details?.weights
  const total = weights ? Object.values(weights).reduce((a, b) => a + b, 0) || 1 : 1
  return (
    <li className="component">
      <div className="component-head">
        <span>{COMPONENT_LABEL[name]}{weights && <span className="muted"> · weight {Math.round((100 * weights[name]) / total)}%</span>}</span>
        <strong>{score === null ? 'Not assessed' : `${Math.round(score)}/100`}</strong>
      </div>
      <div className="bar" role="presentation"><div className="bar-fill" style={{ width: `${score ?? 0}%` }} /></div>
      {info && <p className="muted component-detail">{info.detail}</p>}
    </li>
  )
}

export function MatchPanel({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient()
  const [waiting, setWaiting] = useState(false)

  useEffect(() => {
    if (!waiting) return
    const timer = setTimeout(() => setWaiting(false), 20_000)
    return () => clearTimeout(timer)
  }, [waiting])

  const { data: match, isPending, isError, error } = useQuery({
    queryKey: ['match', jobId],
    queryFn: () => getMatchForJob(jobId),
    refetchInterval: waiting ? 2000 : false,
  })
  const analyze = useMutation({
    mutationFn: () => analyzeJob(jobId),
    onSuccess: () => {
      setWaiting(true)
      queryClient.invalidateQueries({ queryKey: ['match', jobId] })
    },
  })

  return (
    <section className="panel">
      <h2>How well you match</h2>
      {isPending && <p className="muted">Loading…</p>}
      {isError && <p className="notice notice-error" role="alert">{error.message}</p>}
      {match === null && <p className="muted">This job has not been scored yet.</p>}
      {match && (
        <>
          <p className="match-overall">
            <strong>{Math.round(match.overall_score)}%</strong>
            <span className="muted"> estimated fit, based on {Math.round(match.coverage)}% of the criteria</span>
          </p>
          <p className={`notice ${match.eligibility_status === 'ineligible' ? 'notice-error' : match.eligibility_status === 'eligible' ? '' : 'notice-warn'}`}>
            {ELIGIBILITY_TEXT[match.eligibility_status]} {match.details?.location_reasons.join(' ')}
          </p>
          <ul className="components">
            {COMPONENT_KEYS.map((name) => <ComponentRow key={name} match={match} name={name} />)}
          </ul>
          <div className="skill-columns">
            <div><h3>Matched</h3>
              {match.matched_skills.length ? <ul className="chips">{match.matched_skills.map((s) => <li key={s} className="chip chip-remote">{s}</li>)}</ul> : <p className="muted">None found.</p>}
            </div>
            <div><h3>Missing</h3>
              {match.missing_skills.length ? <ul className="chips">{match.missing_skills.map((s) => <li key={s} className="chip">{s}</li>)}</ul> : <p className="muted">None.</p>}
            </div>
          </div>
          {match.uncertain_requirements.length > 0 && (
            <div>
              <h3>Unclear in the listing</h3>
              <ul className="plain-list">{match.uncertain_requirements.map((r) => <li key={r} className="muted">{r}</li>)}</ul>
            </div>
          )}
          <details>
            <summary>How this score was calculated</summary>
            <pre className="explanation">{match.explanation}</pre>
          </details>
          <p className="muted">Uses your confirmed resume facts at calculation time. Scoring version {match.scoring_version}.</p>
        </>
      )}
      <button type="button" className="btn" disabled={analyze.isPending || waiting} onClick={() => analyze.mutate()}>
        <Calculator size={16} aria-hidden="true" /> {match ? 'Recalculate' : 'Score this job'}
      </button>
      {analyze.isError && (
        <p className="notice notice-error" role="alert">
          {analyze.error.message} <Link to="/resume">Go to your resume</Link>
        </p>
      )}
      {waiting && <p className="muted">Calculating… this updates on its own.</p>}
    </section>
  )
}