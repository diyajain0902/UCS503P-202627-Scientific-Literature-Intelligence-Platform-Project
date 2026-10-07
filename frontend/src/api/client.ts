export interface HealthResponse {
  status: string
  version: string
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`, { signal })
  if (!response.ok) {
    throw new Error(`Health check failed with HTTP ${response.status}`)
  }
  return (await response.json()) as HealthResponse
}
