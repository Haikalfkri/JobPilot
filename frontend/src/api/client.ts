const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { credentials: 'include' })
  const body = await response.json().catch(() => null)
  // Health mengembalikan body yang berguna walau 503, jadi tetap diteruskan.
  if (!response.ok && !(body && 'checks' in body)) {
    throw new ApiError(response.status, body?.error?.message ?? 'Request failed')
  }
  return body as T
}