import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { job, paper } from '../test/fixtures'
import { json, mockFetch } from '../test/mockFetch'
import { CorpusView } from './corpus/CorpusView'
import { Dashboard } from './dashboard/Dashboard'
import { HistoryView } from './history/HistoryView'
import { ArxivSearch } from './ingest/ArxivSearch'
import { RecentJobs } from './ingest/RecentJobs'
import { UploadForm } from './ingest/UploadForm'

afterEach(() => vi.unstubAllGlobals())

const page = <T,>(items: T[]) => json({ items, total: items.length, limit: 20, offset: 0 })

describe('UploadForm', () => {
  it('uploads the file as multipart form data and follows the job', async () => {
    const fetch = mockFetch({
      'POST /papers/upload': () => json(job({ kind: 'pdf_upload', display_name: 'My PDF' }), 202),
      'GET /jobs/job-1': () => json(job({ kind: 'pdf_upload', display_name: 'My PDF', state: 'ready' })),
    })
    const onImported = vi.fn()
    render(<UploadForm onImported={onImported} pollIntervalMs={5} />)
    const file = new File(['%PDF-1.7'], 'paper.pdf', { type: 'application/pdf' })
    await userEvent.upload(screen.getByLabelText('PDF file'), file)
    await userEvent.type(screen.getByLabelText('Title (optional)'), 'My PDF')
    await userEvent.click(screen.getByRole('button', { name: 'Upload' }))

    expect(await screen.findByText(/Ready/)).toBeInTheDocument()
    expect(onImported).toHaveBeenCalledTimes(1)
    const body = fetch.mock.calls[0][1]?.body as FormData
    expect(body).toBeInstanceOf(FormData)
    expect((body.get('file') as File).name).toBe('paper.pdf')
    expect(body.get('title')).toBe('My PDF')
    expect(new Headers(fetch.mock.calls[0][1]?.headers).get('Content-Type')).toBeNull()
  })

  it('shows the duplicate-upload conflict from the backend', async () => {
    mockFetch({
      'POST /papers/upload': () =>
        json({ error: { code: 'conflict', message: "This PDF is already in the corpus as 'X'" } }, 409),
    })
    render(<UploadForm onImported={vi.fn()} />)
    await userEvent.upload(screen.getByLabelText('PDF file'), new File(['%PDF'], 'a.pdf'))
    await userEvent.click(screen.getByRole('button', { name: 'Upload' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('already in the corpus')
  })

  it('rejects oversized files before uploading', async () => {
    const fetch = mockFetch({})
    render(<UploadForm onImported={vi.fn()} maxMegabytes={0} />)
    await userEvent.upload(screen.getByLabelText('PDF file'), new File(['%PDF-1.7'], 'big.pdf'))
    await userEvent.click(screen.getByRole('button', { name: 'Upload' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('larger than the 0 MB limit')
    expect(fetch).not.toHaveBeenCalled()
  })
})

describe('ArxivSearch', () => {
  it('lists results, marks papers already in the corpus, and imports new ones', async () => {
    const result = (id: string, stored: number | null) => ({
      arxiv_id: id,
      version: 1,
      title: `Paper ${id}`,
      authors: ['A'],
      abstract: '',
      categories: [],
      published_at: '2020-01-01T00:00:00Z',
      stored_version: stored,
    })
    const fetch = mockFetch({
      'GET /arxiv/search': () => json([result('2101.00001', 1), result('2101.00002', null)]),
      'POST /papers/arxiv': () => json(job({ source_ref: '2101.00002v1' }), 202),
      'GET /jobs/job-1': () => json(job({ source_ref: '2101.00002v1', state: 'ready' })),
    })
    const onImported = vi.fn()
    render(<ArxivSearch onImported={onImported} pollIntervalMs={5} />)
    await userEvent.type(screen.getByLabelText('Keywords'), 'dense retrieval')
    await userEvent.click(screen.getByRole('button', { name: 'Search arXiv' }))

    const list = await screen.findByRole('list', { name: 'arXiv results' })
    const [first, second] = within(list).getAllByRole('listitem')
    expect(first).toHaveTextContent('In corpus (v1)')
    await userEvent.click(within(second).getByRole('button', { name: 'Import' }))
    expect(await within(second).findByText(/Ready/)).toBeInTheDocument()
    expect(onImported).toHaveBeenCalledTimes(1)
    expect(String(fetch.mock.calls[0][0])).toContain('q=dense+retrieval')
    expect(JSON.parse(String(fetch.mock.calls[1][1]?.body))).toEqual({ arxiv_id: '2101.00002v1' })
  })
})

describe('CorpusView', () => {
  it('sends filters to the API', async () => {
    const fetch = mockFetch({
      'GET /categories': () => json(['cs.CL', 'cs.LG']),
      'GET /papers': () => page([paper()]),
    })
    render(<CorpusView refreshKey={0} />)
    expect(await screen.findByText('Synthetic Paper Title')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Title'), 'bert')
    await userEvent.selectOptions(screen.getByLabelText('Source'), 'upload')
    await userEvent.selectOptions(await screen.findByLabelText('Category'), 'cs.CL')
    await userEvent.click(screen.getByRole('button', { name: 'Apply' }))
    await waitFor(() => {
      const urls = fetch.mock.calls.map((c) => String(c[0]))
      expect(urls.some((u) => u.includes('q=bert') && u.includes('source=upload') && u.includes('category=cs.CL'))).toBe(true)
    })
  })

  it('requires confirmation before deleting a paper', async () => {
    let deleted = false
    const fetch = mockFetch({
      'GET /categories': () => json([]),
      'GET /papers': () => page(deleted ? [] : [paper()]),
      'DELETE /papers/paper-1': () => {
        deleted = true
        return new Response(null, { status: 204 })
      },
    })
    render(<CorpusView refreshKey={0} />)
    await userEvent.click(await screen.findByRole('button', { name: 'Synthetic Paper Title' }))
    await userEvent.click(screen.getByRole('button', { name: 'Delete paper' }))
    expect(fetch.mock.calls.some((c) => c[1]?.method === 'DELETE')).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: 'Yes, delete' }))
    expect(await screen.findByText(/No papers match/)).toBeInTheDocument()
    expect(fetch.mock.calls.filter((c) => c[1]?.method === 'DELETE')).toHaveLength(1)
  })
})

describe('RecentJobs', () => {
  it('retries failed jobs', async () => {
    const fetch = mockFetch({
      'GET /jobs': () => json([job({ state: 'failed', error: 'arXiv request timed out', attempts: 1 })]),
      'POST /jobs/job-1/retry': () => json(job({ id: 'job-2' }), 202),
    })
    const onChanged = vi.fn()
    render(<RecentJobs refreshKey={0} onChanged={onChanged} />)
    expect(await screen.findByText('arXiv request timed out')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
    expect(fetch.mock.calls.some((c) => String(c[0]).endsWith('/jobs/job-1/retry'))).toBe(true)
  })
})

describe('Dashboard and history', () => {
  it('shows corpus statistics', async () => {
    mockFetch({
      'GET /stats': () =>
        json({
          papers: 20,
          papers_by_source: { arxiv: 19, upload: 1 },
          chunks: 1634,
          pages: 1207,
          jobs_by_state: { ready: 20 },
          answers_by_status: { answered: 7, insufficient_evidence: 3 },
        }),
      'GET /jobs': () => json([]),
    })
    render(<Dashboard refreshKey={0} />)
    expect(await screen.findByText('1,634')).toBeInTheDocument()
    expect(screen.getByText(/arxiv 19 · upload 1/)).toBeInTheDocument()
  })

  it('opens a saved answer from the history', async () => {
    mockFetch({
      'GET /qa/answer-1': () =>
        json({
          id: 'answer-1',
          query_id: 'q',
          question: 'How many heads?',
          status: 'insufficient_evidence',
          reason: 'Not enough information.',
          claims: [],
          evidence: [],
          generation_model: 'qwen2.5:3b',
          prompt_version: 'qa-v1',
          embedding_model: 'm',
          timings: { retrieval_ms: 1, generation_ms: 1, latency_ms: 2 },
          prompt_tokens: 1,
          completion_tokens: 1,
          created_at: '2026-10-08T00:00:00Z',
        }),
      'GET /qa': () =>
        page([{ id: 'answer-1', question: 'How many heads?', status: 'insufficient_evidence', claim_count: 0, latency_ms: 2, created_at: '2026-10-08T00:00:00Z' }]),
    })
    render(<HistoryView refreshKey={0} />)
    await userEvent.click(await screen.findByRole('button', { name: 'How many heads?' }))
    const saved = await screen.findByRole('region', { name: 'Saved answer' })
    expect(saved).toHaveTextContent('Insufficient evidence. Not enough information.')
  })
})
