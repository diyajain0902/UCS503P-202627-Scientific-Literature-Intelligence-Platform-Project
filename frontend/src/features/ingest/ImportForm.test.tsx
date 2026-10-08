import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { job } from '../../test/fixtures'
import { json, mockFetch } from '../../test/mockFetch'
import { ImportForm } from './ImportForm'

afterEach(() => vi.unstubAllGlobals())

async function importId(id: string) {
  await userEvent.type(screen.getByLabelText('arXiv identifier'), id)
  await userEvent.click(screen.getByRole('button', { name: 'Import' }))
}

describe('ImportForm', () => {
  it('submits an arXiv ID and polls the job until ready', async () => {
    const states = [job({ state: 'embedding' }), job({ state: 'ready', paper_id: 'paper-1' })]
    const fetch = mockFetch({
      'POST /papers/arxiv': () => json(job({ state: 'queued' }), 202),
      'GET /jobs/job-1': () => json(states.shift()),
    })
    const onImported = vi.fn()
    render(<ImportForm onImported={onImported} pollIntervalMs={5} />)

    await importId('2101.00001')

    expect(await screen.findByText(/Ready/)).toBeInTheDocument()
    expect(onImported).toHaveBeenCalledTimes(1)
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ arxiv_id: '2101.00001' })
  })

  it('shows the backend validation message for an invalid ID', async () => {
    mockFetch({
      'POST /papers/arxiv': () =>
        json({ error: { code: 'invalid_input', message: 'not a valid arXiv identifier' } }, 422),
    })
    render(<ImportForm onImported={vi.fn()} />)
    await importId('abc')
    expect(await screen.findByRole('alert')).toHaveTextContent('not a valid arXiv identifier')
  })

  it('shows the job error when ingestion fails', async () => {
    mockFetch({
      'POST /papers/arxiv': () => json(job({ state: 'queued' }), 202),
      'GET /jobs/job-1': () =>
        json(job({ state: 'failed', error: 'PDF is encrypted or password-protected' })),
    })
    const onImported = vi.fn()
    render(<ImportForm onImported={onImported} pollIntervalMs={5} />)
    await importId('2101.00001')
    expect(await screen.findByText(/PDF is encrypted or password-protected/)).toBeInTheDocument()
    expect(onImported).not.toHaveBeenCalled()
  })
})
