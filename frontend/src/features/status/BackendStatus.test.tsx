import { render, screen } from '@testing-library/react'
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
    const list = await screen.findByRole('list', { name: 'Backend dependencies' })
    expect(list).toHaveTextContent('Database: available — pgvector 0.8.0')
    expect(list).toHaveTextContent('Embedding model: unavailable — loading')
    expect(list).toHaveTextContent('Ollama: unavailable — unreachable')
  })

  it('reports an unreachable backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    render(<BackendStatus />)
    expect(await screen.findByRole('status')).toHaveTextContent('Backend unreachable')
  })
})
