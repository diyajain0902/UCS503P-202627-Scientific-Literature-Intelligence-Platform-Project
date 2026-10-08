// Typed client for the backend /api/v1 endpoints. Shapes mirror backend/app/api/v1/schemas.py.

export interface HealthResponse {
  status: string
  version: string
}

export interface CheckResult {
  ok: boolean
  detail: string
}

export interface ReadinessResponse {
  status: 'ready' | 'not_ready'
  checks: Record<string, CheckResult>
}

export type JobState =
  | 'queued'
  | 'fetching'
  | 'extracting'
  | 'chunking'
  | 'embedding'
  | 'ready'
  | 'failed'

export const TERMINAL_STATES: ReadonlySet<JobState> = new Set(['ready', 'failed'])

export interface Job {
  id: string
  kind: string
  state: JobState
  source_ref: string
  display_name: string | null
  paper_id: string | null
  error: string | null
  attempts: number
  created_at: string
  updated_at: string
  finished_at: string | null
}

export interface Paper {
  id: string
  source: string
  arxiv_id: string | null
  arxiv_version: number | null
  title: string
  authors: string[]
  abstract: string | null
  categories: string[]
  published_at: string | null
  page_count: number | null
  chunk_count: number
  created_at: string
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface SearchHit {
  rank: number
  chunk_id: string
  score: number
  text: string
  page_start: number
  page_end: number
  char_start: number
  char_end: number
  paper: { id: string; title: string; arxiv_id: string | null; arxiv_version: number | null }
}

export interface SearchResponse {
  query: string
  top_k: number
  embedding_model: string
  took_ms: number
  results: SearchHit[]
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

async function requestNoContent(path: string, init: RequestInit): Promise<void> {
  await request<unknown>(path, init, [], false)
}

async function request<T>(
  path: string,
  init?: RequestInit,
  acceptStatuses: number[] = [],
  parseBody = true,
): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      // JSON bodies are strings; FormData sets its own multipart boundary header.
      headers: typeof init?.body === 'string' ? { 'Content-Type': 'application/json' } : undefined,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'network_error', 'Cannot reach the backend API')
  }
  if (!response.ok && !acceptStatuses.includes(response.status)) {
    let code = 'http_error'
    let message = `Request failed with HTTP ${response.status}`
    try {
      const body = (await response.json()) as { error?: { code?: string; message?: string } }
      if (body.error?.message) {
        code = body.error.code ?? code
        message = body.error.message
      }
    } catch {
      // Non-JSON error body; keep the generic message.
    }
    throw new ApiError(response.status, code, message)
  }
  return (parseBody ? await response.json() : undefined) as T
}

export const api = {
  health: (signal?: AbortSignal) => request<HealthResponse>('/health', { signal }),
  ready: (signal?: AbortSignal) => request<ReadinessResponse>('/ready', { signal }, [503]),
  importArxiv: (arxivId: string) =>
    request<Job>('/papers/arxiv', { method: 'POST', body: JSON.stringify({ arxiv_id: arxivId }) }),
  job: (id: string, signal?: AbortSignal) => request<Job>(`/jobs/${encodeURIComponent(id)}`, { signal }),
  papers: (limit = 50, offset = 0, signal?: AbortSignal) =>
    request<Page<Paper>>(`/papers?limit=${limit}&offset=${offset}`, { signal }),
  search: (query: string, topK: number) =>
    request<SearchResponse>('/search', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK }),
    }),
  ask: (question: string) =>
    request<QAAnswer>('/qa', { method: 'POST', body: JSON.stringify({ question }) }),
  answer: (id: string) => request<QAAnswer>(`/qa/${encodeURIComponent(id)}`),
  history: (limit = 50, offset = 0) => request<Page<HistoryItem>>(`/qa?limit=${limit}&offset=${offset}`),
  corpus: (filters: PaperFilters, limit = 20, offset = 0, signal?: AbortSignal) => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    for (const [key, value] of Object.entries(filters)) if (value) params.set(key, String(value))
    return request<Page<Paper>>(`/papers?${params.toString()}`, { signal })
  },
  paper: (id: string) => request<Paper>(`/papers/${encodeURIComponent(id)}`),
  deletePaper: (id: string) => requestNoContent(`/papers/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  categories: () => request<string[]>('/categories'),
  upload: (file: File, title: string) => {
    const form = new FormData()
    form.append('file', file)
    if (title.trim()) form.append('title', title.trim())
    return request<Job>('/papers/upload', { method: 'POST', body: form })
  },
  jobs: (limit = 20) => request<Job[]>(`/jobs?limit=${limit}`),
  retryJob: (id: string) => request<Job>(`/jobs/${encodeURIComponent(id)}/retry`, { method: 'POST' }),
  searchArxiv: (query: string) =>
    request<ArxivResult[]>(`/arxiv/search?${new URLSearchParams({ q: query, max_results: '10' })}`),
  stats: () => request<Stats>('/stats'),
  settings: () => request<SettingsInfo>('/settings'),
}

export interface PaperFilters {
  q?: string
  source?: '' | 'arxiv' | 'upload'
  category?: string
  year?: string
}

export interface HistoryItem {
  id: string
  question: string
  status: string
  claim_count: number
  latency_ms: number
  created_at: string
}

export interface ArxivResult {
  arxiv_id: string
  version: number
  title: string
  authors: string[]
  abstract: string
  categories: string[]
  published_at: string | null
  stored_version: number | null
}

export interface Stats {
  papers: number
  papers_by_source: Record<string, number>
  chunks: number
  pages: number
  jobs_by_state: Record<string, number>
  answers_by_status: Record<string, number>
}

export interface SettingsInfo {
  embedding_model: string
  embedding_dimension: number
  chunk_window_tokens: number
  chunk_overlap_tokens: number
  generation_model: string
  generation_options: Record<string, unknown>
  qa_default_top_k: number
  qa_min_score: number
  search_max_top_k: number
  max_pdf_megabytes: number
  max_pdf_pages: number
}

export interface QACitation {
  label: string
  /** True only if the label refers to a passage the model was actually given. */
  valid: boolean
}

export interface QAClaim {
  index: number
  text: string
  /** "cited": has at least one valid citation; semantic support is not verified. */
  support: 'cited' | 'unsupported'
  citations: QACitation[]
}

export interface QAEvidence {
  label: string
  rank: number
  score: number
  chunk_id: string | null
  paper_id: string | null
  paper_title: string
  arxiv_id: string | null
  arxiv_version: number | null
  page_start: number
  page_end: number
  text: string
}

export interface QAAnswer {
  id: string
  query_id: string
  question: string
  status: 'answered' | 'insufficient_evidence' | 'error'
  reason: string | null
  claims: QAClaim[]
  evidence: QAEvidence[]
  generation_model: string | null
  prompt_version: string
  embedding_model: string
  timings: { retrieval_ms: number | null; generation_ms: number | null; latency_ms: number }
  prompt_tokens: number | null
  completion_tokens: number | null
  created_at: string
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

export function formatPages(start: number, end: number): string {
  return start === end ? `p. ${start}` : `pp. ${start}–${end}`
}
