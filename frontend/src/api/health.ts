import { apiGet } from './client'

export type CheckStatus = { status: 'ok' | 'error'; error?: string; model_count?: number }

export type HealthResponse = {
  status: 'ok' | 'degraded'
  checks: { database: CheckStatus; redis: CheckStatus; ollama: CheckStatus }
}

export const fetchHealth = () => apiGet<HealthResponse>('/system/health/')