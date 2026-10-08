import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { QAAnswer } from '../../api/client'
import { json, mockFetch } from '../../test/mockFetch'
import { QAPanel } from './QAPanel'

afterEach(() => vi.unstubAllGlobals())

// Synthetic answer for UI tests only.
const answer = (overrides: Partial<QAAnswer> = {}): QAAnswer => ({
  id: 'answer-1',
  query_id: 'query-1',
  question: 'How many heads?',
  status: 'answered',
  reason: null,
  claims: [
    { index: 0, text: 'The base model uses eight heads.', support: 'cited', citations: [{ label: 'P1', valid: true }] },
    { index: 1, text: 'It won an award.', support: 'unsupported', citations: [{ label: 'P7', valid: false }] },
  ],
  evidence: [
    {
      label: 'P1',
      rank: 1,
      score: 0.61,
      chunk_id: 'chunk-1',
      paper_id: 'paper-1',
      paper_title: 'Synthetic Paper',
      arxiv_id: '2101.00001',
      arxiv_version: 1,
      page_start: 4,
      page_end: 5,
      text: 'Eight attention heads are used in the base model.',
    },
  ],
  generation_model: 'qwen2.5:3b',
  prompt_version: 'qa-v1',
  embedding_model: 'sentence-transformers/all-MiniLM-L6-v2',
  timings: { retrieval_ms: 20, generation_ms: 900, latency_ms: 950 },
  prompt_tokens: 300,
  completion_tokens: 40,
  created_at: '2026-10-08T00:00:00Z',
  ...overrides,
})

async function ask(text: string) {
  await userEvent.type(screen.getByLabelText('Question'), text)
  await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
}

describe('QAPanel', () => {
  it('renders claims with inspectable valid citations and flags invalid ones', async () => {
    const fetch = mockFetch({ 'POST /qa': () => json(answer()) })
    render(<QAPanel />)
    await ask('How many heads?')

    const claims = await screen.findByRole('list', { name: 'Answer claims' })
    expect(claims).toHaveTextContent('The base model uses eight heads.')
    expect(within(claims).getByText('P7 (invalid)')).toBeInTheDocument()
    expect(within(claims).getByText(/Unsupported: no valid citation/)).toBeInTheDocument()
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ question: 'How many heads?' })

    await userEvent.click(screen.getByRole('button', { name: 'Show source P1' }))
    const inspector = screen.getByRole('region', { name: 'Citation inspector' })
    expect(inspector).toHaveTextContent('Synthetic Paper')
    expect(inspector).toHaveTextContent('pp. 4–5')
    expect(inspector).toHaveTextContent('Eight attention heads are used in the base model.')
    expect(screen.queryByRole('button', { name: 'Show source P7' })).not.toBeInTheDocument()
  })

  it('shows an explicit insufficient-evidence message', async () => {
    mockFetch({
      'POST /qa': () =>
        json(answer({ status: 'insufficient_evidence', reason: 'Not enough information.', claims: [] })),
    })
    render(<QAPanel />)
    await ask('Unknowable?')
    expect(await screen.findByRole('status')).toHaveTextContent('Insufficient evidence. Not enough information.')
    expect(screen.queryByRole('list', { name: 'Answer claims' })).not.toBeInTheDocument()
    expect(screen.getByText('Retrieved passages (1)')).toBeInTheDocument()
  })

  it('shows the backend reason when the local model is unavailable', async () => {
    mockFetch({
      'POST /qa': () =>
        json({ error: { code: 'dependency_unavailable', message: 'Ollama is not reachable' } }, 503),
    })
    render(<QAPanel />)
    await ask('Anything?')
    expect(await screen.findByRole('alert')).toHaveTextContent('Ollama is not reachable')
  })
})
