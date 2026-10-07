import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

afterEach(() => vi.unstubAllGlobals())

describe('App', () => {
  it('shows backend version when health check succeeds', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: 'ok', version: '0.1.0' }), { status: 200 }),
      ),
    )
    render(<App />)
    expect(await screen.findByText('Backend online (v0.1.0)')).toBeInTheDocument()
  })

  it('shows an error state when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503 })))
    render(<App />)
    expect(
      await screen.findByText('Backend unreachable: Health check failed with HTTP 503'),
    ).toBeInTheDocument()
  })
})
