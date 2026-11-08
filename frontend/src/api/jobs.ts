import { apiRequest } from './client'

export type WorkArrangement = 'remote' | 'hybrid' | 'onsite' | 'unknown'
export type RemoteEligibility =
  'worldwide' | 'apac' | 'country_specific' | 'region_specific' | 'unknown' | 'not_applicable'
export type ExperienceLevel = 'graduate' | 'junior' | 'associate' | 'mid' | 'senior' | 'unknown'
export type EmploymentType = 'full_time' | 'contract' | 'internship' | 'part_time' | 'unknown'
export type RunStatus = 'pending' | 'running' | 'completed' | 'partial' | 'failed' | 'skipped'

export type JobSummary = {
  id: string
  title: string
  company_name: string
  location_text: string | null
  country_code: string | null
  work_arrangement: WorkArrangement
  remote_eligibility: RemoteEligibility
  eligible_countries: string[] | null
  employment_type: EmploymentType
  experience_level: ExperienceLevel
  salary_min: string | null
  salary_max: string | null
  salary_currency: string | null
  published_at: string | null
  discovered_at: string
  last_verified_at: string | null
  status: 'active' | 'expired' | 'closed' | 'unknown'
  sources: { source_key: string; source_name: string; original_url: string }[]
  match_score: number | null
  match_eligibility: 'eligible' | 'ineligible' | 'uncertain' | 'not_assessed' | null
}

export type JobDetail = JobSummary & {
  description: string
  listings: {
    source_key: string
    source_name: string
    original_url: string
    first_seen_at: string
    last_seen_at: string
    last_checked_at: string | null
    source_status: 'active' | 'closed' | 'unknown'
  }[]
}

export type JobSource = {
  id: string
  key: string
  display_name: string
  base_url: string | null
  is_enabled: boolean
  last_run: { status: RunStatus; finished_at: string | null; error_summary: string | null } | null
}

export type SourceRun = {
  id: string
  source_key: string
  source_name: string
  status: RunStatus
  fetched_count: number
  created_count: number
  updated_count: number
  ignored_count: number
  error_code: string | null
  error_summary: string | null
}

export type DiscoveryRun = {
  id: string
  status: RunStatus
  trigger_type: 'manual' | 'scheduled'
  started_at: string
  finished_at: string | null
  criteria: { source_keys: string[]; keywords: string[] }
  summary: { fetched?: number; created?: number; updated?: number; ignored?: number; error?: string }
  source_runs: SourceRun[]
}

export type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] }

export type JobFilters = Partial<Record<
  'q' | 'work_arrangement' | 'remote_eligibility' | 'experience_level' | 'published_within_days' | 'page'
  | 'min_match_score' | 'hide_ineligible' | 'ordering',
  string
>>

function toQuery(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => value && search.set(key, value))
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const listJobs = (filters: JobFilters) => apiRequest<Paginated<JobSummary>>(`/jobs/${toQuery(filters)}`)
export const getJob = (id: string) => apiRequest<JobDetail>(`/jobs/${id}/`)
export const verifyJob = (id: string) =>
  apiRequest<{ job_id: string; status: string }>(`/jobs/${id}/verify/`, { method: 'POST' })

export const listSources = () => apiRequest<JobSource[]>('/job-sources/')
export const setSourceEnabled = (id: string, is_enabled: boolean) =>
  apiRequest<JobSource>(`/job-sources/${id}/`, { method: 'PATCH', json: { is_enabled } })

export const startDiscovery = (body: { keywords?: string[] }) =>
  apiRequest<{ discovery_run_id: string; status: RunStatus }>('/jobs/discover/', { method: 'POST', json: body })
export const listRuns = () =>
  apiRequest<Paginated<DiscoveryRun>>('/jobs/discovery-runs/').then((page) => page.results)

export const isActiveRun = (status: RunStatus) => status === 'pending' || status === 'running'

// ---------- display helpers ----------

export const WORK_LABEL: Record<WorkArrangement, string> = {
  remote: 'Remote', hybrid: 'Hybrid', onsite: 'On-site', unknown: 'Work arrangement not stated',
}
export const LEVEL_LABEL: Record<ExperienceLevel, string> = {
  graduate: 'Graduate', junior: 'Junior', associate: 'Associate', mid: 'Mid-level', senior: 'Senior',
  unknown: 'Level not stated',
}
export const TYPE_LABEL: Record<EmploymentType, string> = {
  full_time: 'Full-time', contract: 'Contract', internship: 'Internship', part_time: 'Part-time',
  unknown: 'Type not stated',
}

export function eligibilityLabel(job: Pick<JobSummary, 'remote_eligibility' | 'eligible_countries'>): string | null {
  const where = job.eligible_countries?.join(', ')
  switch (job.remote_eligibility) {
    case 'worldwide': return 'Open to applicants worldwide'
    case 'apac': return 'Open to applicants in APAC'
    case 'country_specific': return `Restricted to: ${where}`
    case 'region_specific': return `Restricted to: ${where}`
    case 'unknown': return 'Who can apply is not stated. Check the listing.'
    default: return null
  }
}