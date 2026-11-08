import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { activateResume, listResumes, reprocessResume, type ParsingStatus, type Resume } from '../../api/resumes'

const STATUS_LABEL: Record<ParsingStatus, string> = {
  pending: 'Waiting to parse',
  processing: 'Parsing…',
  review_required: 'Needs review',
  completed: 'Reviewed',
  failed: 'Failed',
}

type Props = { selectedId: string | null; onSelect: (id: string) => void }

export function VersionList({ selectedId, onSelect }: Props) {
  const queryClient = useQueryClient()
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['resumes'],
    queryFn: listResumes,
    // Keep polling while any version is still being parsed.
    refetchInterval: (query) =>
      query.state.data?.some((r) => r.parsing_status === 'pending' || r.parsing_status === 'processing')
        ? 2000
        : false,
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['resumes'] })
    queryClient.invalidateQueries({ queryKey: ['facts'] })
  }
  const activate = useMutation({ mutationFn: activateResume, onSuccess: refresh })
  const reprocess = useMutation({ mutationFn: reprocessResume, onSuccess: refresh })
  const actionError = activate.error ?? reprocess.error

  if (isPending) return <p className="muted">Loading versions…</p>
  if (isError) return <p className="notice notice-error" role="alert">{error.message}</p>
  if (data.length === 0) {
    return <p className="muted">No resume yet. Upload your master resume to get started.</p>
  }

  const canActivate = (r: Resume) =>
    !r.is_active && (r.parsing_status === 'review_required' || r.parsing_status === 'completed')
  const busy = (r: Resume) => r.parsing_status === 'pending' || r.parsing_status === 'processing'

  return (
    <section>
      <h2>Versions</h2>
      {actionError && <p className="notice notice-error" role="alert">{actionError.message}</p>}
      <ul className="version-list">
        {data.map((resume) => (
          <li key={resume.id} className={resume.id === selectedId ? 'version selected' : 'version'}>
            <button type="button" className="version-main" onClick={() => onSelect(resume.id)}
              aria-current={resume.id === selectedId}>
              <strong>Version {resume.version_number}</strong>
              {resume.is_active && <span className="badge badge-active">Active</span>}
              <span className="muted">{resume.filename}</span>
              <span className={`badge badge-${resume.parsing_status}`}>{STATUS_LABEL[resume.parsing_status]}</span>
              {resume.parsing_status === 'failed' && <span className="muted">{resume.parsing_error}</span>}
              {(resume.parsing_status === 'review_required' || resume.parsing_status === 'completed') && (
                <span className="muted">
                  {resume.fact_counts.user_confirmed} confirmed, {resume.fact_counts.parser_suggested} to review
                </span>
              )}
            </button>
            <div className="version-actions">
              {canActivate(resume) && (
                <button type="button" className="btn" disabled={activate.isPending}
                  onClick={() => activate.mutate(resume.id)}>Make active</button>
              )}
              <button type="button" className="btn" disabled={busy(resume) || reprocess.isPending}
                onClick={() => reprocess.mutate(resume.id)}>Parse again</button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}