import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Analysis } from '../../api/client'
import { paper } from '../../test/fixtures'
import { json, mockFetch } from '../../test/mockFetch'
import { CompareView } from './CompareView'
import { PaperAnalysis } from './PaperAnalysis'

afterEach(() => vi.unstubAllGlobals())

// Synthetic analysis results for UI tests only.
const evidence = {
  label: 'P1',
  chunk_id: 'c1',
  paper_id: 'paper-1',
  paper_title: 'Synthetic Paper Title',
  arxiv_id: '2101.00001',
  arxiv_version: 2,
  page_start: 3,
  page_end: 3,
  score: 0.5,
  text: 'We evaluate on LongDocs.',
}
const analysis = (overrides: Partial<Analysis>): Analysis => ({
  id: 'a1',
  kind: 'summary',
  paper_ids: ['paper-1'],
  topic: null,
  status: 'completed',
  reason: null,
  result: {},
  evidence: [evidence],
  generation_model: 'qwen2.5:3b',
  prompt_version: 'analysis-v1',
  latency_ms: 900,
  created_at: '2026-10-08T00:00:00Z',
  ...overrides,
})

describe('PaperAnalysis', () => {
  it('shows a cited summary with an inspectable source', async () => {
    mockFetch({
      'POST /papers/paper-1/summary': () =>
        json(
          analysis({
            result: { claims: [{ index: 0, text: 'The paper evaluates on LongDocs.', support: 'cited', citations: [{ label: 'P1', valid: true }] }] },
          }),
        ),
    })
    render(<PaperAnalysis paperId="paper-1" />)
    await userEvent.click(screen.getByRole('button', { name: 'Summarise' }))
    expect(await screen.findByRole('list', { name: 'summary claims' })).toHaveTextContent('The paper evaluates on LongDocs.')
    await userEvent.click(screen.getByRole('button', { name: 'Show source P1' }))
    expect(screen.getByRole('region', { name: 'Citation inspector' })).toHaveTextContent('p. 3')
  })

  it('marks unknown extracted fields', async () => {
    mockFetch({
      'POST /papers/paper-1/extraction': () =>
        json(
          analysis({
            kind: 'extraction',
            result: {
              fields: [
                { field: 'dataset', value: 'LongDocs', status: 'found', citations: [{ label: 'P1', valid: true }] },
                { field: 'metric', value: 'unknown', status: 'unknown', citations: [] },
              ],
            },
          }),
        ),
    })
    render(<PaperAnalysis paperId="paper-1" />)
    await userEvent.click(screen.getByRole('button', { name: 'Extract key facts' }))
    const table = await screen.findByRole('table', { name: 'Extracted fields' })
    expect(within(table).getByRole('row', { name: /Dataset/ })).toHaveTextContent('LongDocs')
    expect(within(table).getByRole('row', { name: /Metric/ })).toHaveTextContent('Unknown (not stated')
  })

  it('reports insufficient evidence instead of a summary', async () => {
    mockFetch({
      'POST /papers/paper-1/summary': () =>
        json(analysis({ status: 'insufficient_evidence', reason: 'The passages did not support any cited statement.' })),
    })
    render(<PaperAnalysis paperId="paper-1" />)
    await userEvent.click(screen.getByRole('button', { name: 'Summarise' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Insufficient evidence.')
  })
})

describe('CompareView', () => {
  it('compares selected papers side by side and shows caveats', async () => {
    const fetch = mockFetch({
      'GET /papers': () =>
        json({ items: [paper(), paper({ id: 'paper-2', title: 'Second Paper' })], total: 2, limit: 100, offset: 0 }),
      'POST /compare': () =>
        json({
          fields: ['dataset', 'result'],
          caveats: ['Results were reported on different datasets or settings; they are not directly comparable.'],
          papers: [
            { paper_id: 'paper-1', title: 'Synthetic Paper Title', analysis_id: 'a1', fields: { dataset: { field: 'dataset', value: 'LongDocs', status: 'found', citations: [] } } },
            { paper_id: 'paper-2', title: 'Second Paper', analysis_id: 'a2', fields: {} },
          ],
        }),
    })
    render(<CompareView refreshKey={0} />)
    const compareButton = screen.getByRole('button', { name: 'Compare key facts' })
    expect(compareButton).toBeDisabled()
    await userEvent.click(await screen.findByLabelText('Synthetic Paper Title'))
    await userEvent.click(screen.getByLabelText('Second Paper'))
    await userEvent.click(compareButton)

    const table = await screen.findByRole('table', { name: 'Paper comparison' })
    expect(within(table).getByRole('row', { name: /Dataset/ })).toHaveTextContent('LongDocsUnknown')
    expect(screen.getByRole('note')).toHaveTextContent('not directly comparable')
    const body = JSON.parse(String(fetch.mock.calls.find((c) => String(c[0]).endsWith('/compare'))?.[1]?.body))
    expect(body).toEqual({ paper_ids: ['paper-1', 'paper-2'] })
  })
})
