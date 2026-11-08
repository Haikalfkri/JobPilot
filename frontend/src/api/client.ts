const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type RequestOptions = { method?: string; json?: unknown; formData?: FormData }

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

// Turns the API's error envelope into one readable sentence.
function errorMessage(body: unknown): string {
  const error = isRecord(body) && isRecord(body.error) ? body.error : null
  if (!error) return 'Request failed'
  if (error.code === 'VALIDATION_ERROR' && isRecord(error.details)) {
    const first = Object.values(error.details).flat()[0]
    if (typeof first === 'string') return first
  }
  return typeof error.message === 'string' ? error.message : 'Request failed'
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const init: RequestInit = { method: options.method ?? 'GET', credentials: 'include' }
  if (options.json !== undefined) {
    init.headers = { 'Content-Type': 'application/json' }
    init.body = JSON.stringify(options.json)
  } else if (options.formData) {
    init.body = options.formData // the browser sets the multipart boundary itself
  }

  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new ApiError(0, 'Cannot reach the backend. Is it running?')
  }
  const body: unknown = await response.json().catch(() => null)
  // The health endpoint returns a useful body on 503, so callers still get it.
  if (!response.ok && !(isRecord(body) && 'checks' in body)) {
    throw new ApiError(response.status, errorMessage(body))
  }
  return body as T
}

export const apiGet = <T,>(path: string) => apiRequest<T>(path)