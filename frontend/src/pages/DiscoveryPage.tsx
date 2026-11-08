import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Play } from 'lucide-react'
import { useState } from 'react'
import {
  isActiveRun, listRuns, listSources, setSourceEnabled, startDiscovery, type DiscoveryRun, type RunStatus,
} from '../api/jobs'
import { getPreferences } from '../api/matching'
import { formatDateTime } from '../lib/format'

const STATUS_LABEL: Record<RunStatus, string> = {
  pending: 'Queued', running: 'Running…', completed: 'Completed', partial: 'Partly completed',
  failed: 'Failed', skipped: 'Skipped',
}

function RunCard({ run }: { run: DiscoveryRun }) {
  const { summary } = run
  return (
    <li className="run">
      <div className="run-head">
        <span className={`badge badge-${run.status}`}>{STATUS_LABEL[run.status]}</span>
        <span>{formatDateTime(run.started_at)}</span>
        <span className="muted">{run.trigger_type === 'scheduled' ? 'Scheduled' : 'Manual'}</span>
      </div>
      {run.criteria.keywords.length > 0 && <p className="muted">Keywords: {run.criteria.keywords.join(', ')}</p>}
      {summary.error && <p className="notice notice-error">{summary.error}</p>}
      {summary.created !== undefined && (
        <p className="muted">
          {summary.fetched} fetched: {summary.created} new, {summary.updated} updated, {summary.ignored} unchanged or skipped
        </p>
      )}
      <ul className="source-runs">
        {run.source_runs.map((sr) => (
          <li key={sr.id}>
            <strong>{sr.source_name}</strong> <span className={`badge badge-${sr.status}`}>{STATUS_LABEL[sr.status]}</span>
            <span className="muted"> {sr.fetched_count} fetched, {sr.created_count} new</span>
            {sr.error_summary && <p className="notice notice-warn">{sr.error_summary}</p>}
          </li>
        ))}
      </ul>
    </li>
  )
}

export function DiscoveryPage() {
  const queryClient = useQueryClient()
  const [keywordText, setKeywordText] = useState('')

  const sources = useQuery({ queryKey: ['sources'], queryFn: listSources })
  const preferences = useQuery({ queryKey: ['preferences'], queryFn: getPreferences })
  const savedKeywords = preferences.data?.keywords ?? []
  const runs = useQuery({
    queryKey: ['runs'],
    queryFn: listRuns,
    refetchInterval: (query) => (query.state.data?.some((r) => isActiveRun(r.status)) ? 2000 : false),
  })
  const running = runs.data?.some((r) => isActiveRun(r.status)) ?? false

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['runs'] })
    queryClient.invalidateQueries({ queryKey: ['sources'] })
    queryClient.invalidateQueries({ queryKey: ['jobs'] })
  }
  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => setSourceEnabled(id, enabled),
    onSuccess: refresh,
  })
  const start = useMutation({ mutationFn: startDiscovery, onSuccess: refresh })

  const keywords = keywordText.split(',').map((k) => k.trim()).filter(Boolean)
  const enabledCount = sources.data?.filter((s) => s.is_enabled).length ?? 0

  return (
    <div className="page">
      <h1>Discovery</h1>

      <section className="panel">
        <h2>Sources</h2>
        <p className="muted">
          Only sources with a public API are used. Each makes at most a handful of requests per run, and every job
          keeps a link back to where it was listed.
        </p>
        {sources.isPending && <p className="muted">Loading sources…</p>}
        {sources.isError && <p className="notice notice-error" role="alert">{sources.error.message}</p>}
        <ul className="source-toggles">
          {sources.data?.map((source) => (
            <li key={source.id}>
              <label>
                <input type="checkbox" checked={source.is_enabled} disabled={toggle.isPending}
                  onChange={(event) => toggle.mutate({ id: source.id, enabled: event.target.checked })} />
                <strong>{source.display_name}</strong>
              </label>
              <span className="muted">
                {source.last_run ? `Last run: ${STATUS_LABEL[source.last_run.status]}` : 'Never run'}
              </span>
            </li>
          ))}
        </ul>
        {toggle.isError && <p className="notice notice-error" role="alert">{toggle.error.message}</p>}
      </section>

      <section className="panel">
        <h2>Run discovery</h2>
        <label className="field">
          <span>Keywords (comma-separated, optional)</span>
          <input type="text" value={keywordText} placeholder={savedKeywords.length ? `Leave empty to use your saved keywords: ${savedKeywords.join(', ')}` : 'Leave empty to use the default keywords'}
            onChange={(event) => setKeywordText(event.target.value)} />
        </label>
        <button type="button" className="btn btn-primary" disabled={start.isPending || running || enabledCount === 0}
          onClick={() => start.mutate(keywords.length ? { keywords } : savedKeywords.length ? { keywords: savedKeywords } : {})}>
          <Play size={16} aria-hidden="true" /> {running ? 'A run is in progress…' : 'Run discovery'}
        </button>
        {enabledCount === 0 && <p className="muted">Enable at least one source first.</p>}
        {start.isError && <p className="notice notice-error" role="alert">{start.error.message}</p>}
      </section>

      <section>
        <h2>Recent runs</h2>
        {runs.isPending && <p className="muted">Loading runs…</p>}
        {runs.isError && <p className="notice notice-error" role="alert">{runs.error.message}</p>}
        {runs.data?.length === 0 && <p className="muted">No runs yet.</p>}
        <ul className="run-list">{runs.data?.map((run) => <RunCard key={run.id} run={run} />)}</ul>
      </section>
    </div>
  )
}