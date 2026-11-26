import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { job, paper } from '../test/fixtures'
import { json, mockFetch } from '../test/mockFetch'
import { CorpusView } from './corpus/CorpusView'
import { HomeView } from './dashboard/HomeView'
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
    expect(screen.getByText('paper.pdf')).toBeInTheDocument()
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
  it('lists results, marks papers already in the library, and imports new ones', async () => {
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
    await userEvent.type(screen.getByLabelText('Search arXiv'), 'dense retrieval')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))

    const list = await screen.findByRole('list', { name: 'arXiv results' })
    const [first, second] = within(list).getAllByRole('listitem')
    expect(within(first).getByText('Added ✓')).toHaveAttribute('title', 'In your library as v1')
    await userEvent.click(within(second).getByRole('button', { name: 'Add' }))
    expect(await within(second).findByText(/Ready/)).toBeInTheDocument()
    expect(onImported).toHaveBeenCalledTimes(1)
    expect(String(fetch.mock.calls[0][0])).toContain('q=dense+retrieval')
    expect(JSON.parse(String(fetch.mock.calls[1][1]?.body))).toEqual({ arxiv_id: '2101.00002v1' })
  })

  it('imports an arXiv ID directly and polls the job until ready', async () => {
    const states = [job({ state: 'embedding' }), job({ state: 'ready', paper_id: 'paper-1' })]
    const fetch = mockFetch({
      'POST /papers/arxiv': () => json(job({ state: 'queued' }), 202),
      'GET /jobs/job-1': () => json(states.shift()),
    })
    const onImported = vi.fn()
    render(<ArxivSearch onImported={onImported} pollIntervalMs={5} />)
    await userEvent.type(screen.getByLabelText('Search arXiv'), '2101.00001')
    await userEvent.click(screen.getByRole('button', { name: 'Import' }))

    expect(await screen.findByText(/Ready/)).toBeInTheDocument()
    expect(onImported).toHaveBeenCalledTimes(1)
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ arxiv_id: '2101.00001' })
  })

  it('shows the backend validation message for a rejected ID', async () => {
    mockFetch({
      'POST /papers/arxiv': () => json({ error: { code: 'invalid_input', message: 'not a valid arXiv identifier' } }, 422),
    })
    render(<ArxivSearch onImported={vi.fn()} />)
    await userEvent.type(screen.getByLabelText('Search arXiv'), '9999.99999')
    await userEvent.click(screen.getByRole('button', { name: 'Import' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('not a valid arXiv identifier')
  })

  it('shows the job error when ingestion fails', async () => {
    mockFetch({
      'POST /papers/arxiv': () => json(job({ state: 'queued' }), 202),
      'GET /jobs/job-1': () => json(job({ state: 'failed', error: 'PDF is encrypted or password-protected' })),
    })
    const onImported = vi.fn()
    render(<ArxivSearch onImported={onImported} pollIntervalMs={5} />)
    await userEvent.type(screen.getByLabelText('Search arXiv'), '2101.00001')
    await userEvent.click(screen.getByRole('button', { name: 'Import' }))
    expect(await screen.findByText(/PDF is encrypted or password-protected/)).toBeInTheDocument()
    expect(onImported).not.toHaveBeenCalled()
  })
})

describe('CorpusView', () => {
  it('sends filters to the API', async () => {
    const fetch = mockFetch({
      'GET /categories': () => json(['cs.CL', 'cs.LG']),
      'GET /papers': () => page([paper()]),
      'GET /jobs': () => json([]),
    })
    render(<CorpusView refreshKey={0} />)
    expect(await screen.findByText('Synthetic Paper Title')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Filter papers'), 'bert')
    await userEvent.click(screen.getByRole('button', { name: 'Uploads' }))
    await userEvent.selectOptions(await screen.findByLabelText('Category'), 'cs.CL')
    await waitFor(() => {
      const urls = fetch.mock.calls.map((c) => String(c[0]))
      expect(urls.some((u) => u.includes('q=bert') && u.includes('source=upload') && u.includes('category=cs.CL'))).toBe(true)
    })
  })

  it('opens a paper in a drawer and requires confirmation before deleting it', async () => {
    let deleted = false
    const fetch = mockFetch({
      'GET /categories': () => json([]),
      'GET /papers': () => page(deleted ? [] : [paper()]),
      'GET /jobs': () => json([]),
      'DELETE /papers/paper-1': () => {
        deleted = true
        return new Response(null, { status: 204 })
      },
    })
    const onChanged = vi.fn()
    render(<CorpusView refreshKey={0} onChanged={onChanged} />)
    await userEvent.click(await screen.findByRole('button', { name: /Synthetic Paper Title/ }))
    const drawer = screen.getByRole('dialog', { name: 'Details for Synthetic Paper Title' })
    await userEvent.click(within(drawer).getByRole('button', { name: 'Delete paper' }))
    expect(fetch.mock.calls.some((c) => c[1]?.method === 'DELETE')).toBe(false)
    await userEvent.click(within(drawer).getByRole('button', { name: 'Yes, delete' }))
    expect(await screen.findByText(/No papers match/)).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(fetch.mock.calls.filter((c) => c[1]?.method === 'DELETE')).toHaveLength(1)
    expect(onChanged).toHaveBeenCalled()
  })

  it('closes the paper drawer on Escape and on a scrim click', async () => {
    mockFetch({
      'GET /categories': () => json([]),
      'GET /papers': () => page([paper()]),
      'GET /jobs': () => json([]),
    })
    render(<CorpusView refreshKey={0} />)
    const card = await screen.findByRole('button', { name: /Synthetic Paper Title/ })
    await userEvent.click(card)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await userEvent.click(card)
    await userEvent.click(screen.getByTestId('scrim'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
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

  it('hides failures that a later attempt for the same source has superseded', async () => {
    mockFetch({
      'GET /jobs': () =>
        json([
          job({ id: 'job-2', state: 'embedding', created_at: '2026-10-09T00:00:00Z', display_name: 'Retried paper' }),
          job({ id: 'job-1', state: 'failed', error: 'arXiv request timed out', created_at: '2026-10-08T00:00:00Z' }),
        ]),
    })
    render(<RecentJobs refreshKey={0} onChanged={vi.fn()} pollIntervalMs={60000} />)
    expect(await screen.findByText('Retried paper')).toBeInTheDocument()
    expect(screen.getByText('Computing embeddings')).toBeInTheDocument()
    expect(screen.queryByText('arXiv request timed out')).not.toBeInTheDocument()
  })

  it('refreshes the library when a running job finishes', async () => {
    const responses = [[job({ state: 'chunking' })], [job({ state: 'ready' })]]
    mockFetch({ 'GET /jobs': () => json(responses.length > 1 ? responses.shift() : responses[0]) })
    const onChanged = vi.fn()
    render(<RecentJobs refreshKey={0} onChanged={onChanged} pollIntervalMs={5} />)
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1))
  })
})

describe('Home and history', () => {
  const stats = {
    papers: 20,
    papers_by_source: { arxiv: 19, upload: 1 },
    chunks: 1634,
    pages: 1207,
    jobs_by_state: { ready: 20 },
    answers_by_status: { answered: 7, insufficient_evidence: 3 },
  }

  it('shows library statistics, recent questions and suggestions from the newest papers', async () => {
    mockFetch({
      'GET /stats': () => json(stats),
      'GET /qa': () =>
        page([{ id: 'a1', question: 'How many heads?', status: 'answered', claim_count: 1, latency_ms: 900, created_at: '2026-10-08T00:00:00Z' }]),
      'GET /papers': () => page([paper({ title: 'Attention Is All You Need' })]),
      'GET /jobs': () => json([]),
    })
    const onAsk = vi.fn()
    const onOpenAnswer = vi.fn()
    render(<HomeView refreshKey={0} onAsk={onAsk} onOpenAnswer={onOpenAnswer} onNavigate={vi.fn()} onAddPapers={vi.fn()} />)
    const line = await screen.findByLabelText('Library statistics')
    expect(line).toHaveTextContent('20 papers')
    expect(line).toHaveTextContent('1,634 passages')
    expect(line).toHaveTextContent('10 answers')
    await userEvent.click(screen.getByRole('button', { name: 'What is the main contribution of Attention Is All You Need?' }))
    expect(onAsk).toHaveBeenCalledWith('What is the main contribution of Attention Is All You Need?')
    await userEvent.click(screen.getByRole('button', { name: /How many heads\?/ }))
    expect(onOpenAnswer).toHaveBeenCalledWith('a1')
  })

  it('shows an indexing banner while papers are being processed', async () => {
    mockFetch({
      'GET /stats': () => json(stats),
      'GET /qa': () => page([]),
      'GET /papers': () => page([]),
      'GET /jobs': () => json([job({ state: 'embedding', display_name: 'LoRA' }), job({ id: 'job-2', state: 'ready' })]),
    })
    const onNavigate = vi.fn()
    render(<HomeView refreshKey={0} onAsk={vi.fn()} onOpenAnswer={vi.fn()} onNavigate={onNavigate} onAddPapers={vi.fn()} pollIntervalMs={60000} />)
    const banner = await screen.findByRole('button', { name: /Indexing 1 paper — LoRA: Computing embeddings/ })
    await userEvent.click(banner)
    expect(onNavigate).toHaveBeenCalledWith('library')
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
    await userEvent.click(await screen.findByRole('button', { name: /How many heads\?/ }))
    const saved = await screen.findByRole('region', { name: 'Saved answer' })
    expect(saved).toHaveTextContent('Not in your papers. Not enough information.')
  })
})
