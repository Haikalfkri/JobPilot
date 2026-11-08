import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '../api/health'

const LABELS = { database: 'Database', redis: 'Task queue', ollama: 'Local AI' } as const

export function HealthIndicator() {
  const { data, isPending, isError } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
    retry: false,
  })

  const state = isPending ? 'pending' : isError ? 'offline' : data.status
  const summary = {
    pending: 'Checking services…',
    offline: 'Backend unreachable',
    ok: 'All services running',
    degraded: 'Some services are down',
  }[state]

  return (
    <div className="health" role="status" aria-live="polite">
      <div className="health-summary">
        <span className={`dot dot-${state}`} aria-hidden="true" />
        {summary}
      </div>
      {data && (
        <ul className="health-list">
          {(Object.keys(LABELS) as (keyof typeof LABELS)[]).map((key) => (
            <li key={key}>
              <span className={`dot dot-${data.checks[key].status}`} aria-hidden="true" />
              {LABELS[key]}
              <span className="sr-only">: {data.checks[key].status === 'ok' ? 'running' : 'down'}</span>
            </li>
          ))}
        </ul>
      )}
      {isError && <p className="health-hint">Start the backend, then this updates on its own.</p>}
    </div>
  )
}