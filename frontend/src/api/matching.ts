import { apiRequest } from './client'

export type Arrangement = 'remote' | 'hybrid' | 'onsite'
export type Level = 'graduate' | 'junior' | 'associate' | 'mid' | 'senior'
export type ComponentKey = 'skills' | 'experience' | 'title' | 'seniority' | 'location'
export type Eligibility = 'eligible' | 'ineligible' | 'uncertain' | 'not_assessed'

export const COMPONENT_KEYS: ComponentKey[] = ['skills', 'experience', 'title', 'seniority', 'location']
export const ARRANGEMENTS: Arrangement[] = ['remote', 'hybrid', 'onsite']
export const LEVELS: Level[] = ['graduate', 'junior', 'associate', 'mid', 'senior']

export type TargetLocation = {
  label: string
  country_code: string | null
  city: string | null
  arrangements: Arrangement[]
}

export type Preferences = {
  job_titles: string[]
  keywords: string[]
  target_locations: TargetLocation[]
  work_arrangements: Arrangement[]
  employment_types: string[]
  experience_levels: Level[]
  candidate_countries: string[]
  component_weights: Record<ComponentKey, number>
  minimum_match_score: number
  publication_window_days: number
  updated_at: string
}

export type Match = {
  id: string
  job_id: string
  job_title: string
  company_name: string
  overall_score: number
  coverage: number
  components: Record<ComponentKey, number | null>
  eligibility_status: Eligibility
  matched_skills: string[]
  missing_skills: string[]
  uncertain_requirements: string[]
  scoring_version: string
  calculated_at: string
  explanation?: string
  details?: {
    weights: Record<ComponentKey, number>
    components: Record<ComponentKey, { score: number | null; detail: string }>
    location_reasons: string[]
    candidate: { confirmed_facts: number; estimated_years: number | null; implied_skills: string[] }
  }
}

type Page<T> = { count: number; results: T[] }

export const getPreferences = () => apiRequest<Preferences>('/settings/search-preferences/')
export const savePreferences = (data: Partial<Preferences>) =>
  apiRequest<Preferences>('/settings/search-preferences/', { method: 'PUT', json: data })

export async function getMatchForJob(jobId: string): Promise<Match | null> {
  const page = await apiRequest<Page<Match>>(`/matching/results/?job_id=${jobId}`)
  if (page.results.length === 0) return null
  return apiRequest<Match>(`/matching/results/${page.results[0].id}/`)
}

export const analyzeJob = (jobId: string) =>
  apiRequest<{ status: string }>(`/matching/jobs/${jobId}/analyze/`, { method: 'POST' })
export const recalculateAll = () => apiRequest<{ status: string }>('/matching/recalculate/', { method: 'POST' })

export const ELIGIBILITY_TEXT: Record<Eligibility, string> = {
  eligible: 'You can apply, going by the rules stated in the listing.',
  ineligible: 'Not open to you, going by the rules stated in the listing.',
  uncertain: 'Eligibility is unclear. Check the listing before applying.',
  not_assessed: 'Eligibility was not assessed. Set the countries you can work in under Settings.',
}
export const COMPONENT_LABEL: Record<ComponentKey, string> = {
  skills: 'Skills', experience: 'Experience', title: 'Job title', seniority: 'Seniority', location: 'Location',
}