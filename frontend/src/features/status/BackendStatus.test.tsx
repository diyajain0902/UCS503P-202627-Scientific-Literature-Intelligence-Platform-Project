import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { json, mockFetch } from '../../test/mockFetch'
import { BackendStatus } from './BackendStatus'

afterEach(() => vi.unstubAllGlobals())

describe('BackendStatus', () => {
  it('shows each dependency even when the backend reports not ready', async () => {
    mockFetch({
      'GET /ready': () =>
        json(
          {
            status: 'not_ready',
            checks: {
              database: { ok: true, detail: 'pgvector 0.8.0, schema revision 0001' },
              embedding_model: { ok: false, detail: 'loading' },
              ollama: { ok: false, detail: 'unreachable (ConnectError)' },
            },
          },
          503,
        ),
    })
    render(<BackendStatus />)
    await userEvent.click(await screen.findByRole('button', { name: 'Not ready' }))
    const list = screen.getByRole('list', { name: 'Backend dependencies' })
    expect(list).toHaveTextContent('Database: available — pgvector 0.8.0')
    expect(list).toHaveTextContent('Embeddings: unavailable — loading')
    expect(list).toHaveTextContent('Ollama: unavailable — unreachable')
    expect(screen.getByRole('status')).toHaveTextContent('Backend not ready: Embeddings, Ollama')
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('list', { name: 'Backend dependencies' })).not.toBeInTheDocument()
  })

  it('reports an unreachable backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    render(<BackendStatus />)
    expect(await screen.findByRole('status')).toHaveTextContent('Backend unreachable')
  })
})
