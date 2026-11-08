import { apiRequest } from './client'

export type ParsingStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'review_required'
export type VerificationStatus = 'parser_suggested' | 'user_confirmed' | 'rejected'

export const FACT_CATEGORIES = [
  'personal', 'link', 'summary', 'experience', 'education',
  'skill', 'project', 'certification', 'language',
] as const
export type FactCategory = (typeof FACT_CATEGORIES)[number]

export type Resume = {
  id: string
  filename: string
  version_number: number
  file_type: 'pdf' | 'docx'
  parsing_status: ParsingStatus
  parsing_error: string
  is_active: boolean
  uploaded_at: string
  fact_counts: Record<VerificationStatus, number>
}
export type UploadedResume = Resume & { duplicate_of_version: number | null }

export type Fact = {
  id: string
  category: FactCategory
  fact_key: string | null
  content: string
  source_location: string
  verification_status: VerificationStatus
}

type Page<T> = { count: number; results: T[] }

export const listResumes = () => apiRequest<Page<Resume>>('/resumes/').then((page) => page.results)

export function uploadResume(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return apiRequest<UploadedResume>('/resumes/upload/', { method: 'POST', formData })
}

export const activateResume = (id: string) =>
  apiRequest<Resume>(`/resumes/${id}/activate/`, { method: 'POST' })

export const reprocessResume = (id: string) =>
  apiRequest<Resume>(`/resumes/${id}/reprocess/`, { method: 'POST' })

export const listFacts = (resumeId: string) =>
  apiRequest<Page<Fact>>(`/resumes/${resumeId}/facts/`).then((page) => page.results)

export const updateFact = (
  id: string,
  data: { content?: string; verification_status?: 'user_confirmed' | 'rejected' },
) => apiRequest<Fact>(`/resume-facts/${id}/`, { method: 'PATCH', json: data })

export const createFact = (resumeId: string, data: { category: FactCategory; content: string }) =>
  apiRequest<Fact>(`/resumes/${resumeId}/facts/`, { method: 'POST', json: data })