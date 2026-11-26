import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { json, mockFetch } from './test/mockFetch'

const empty = () => json({ items: [], total: 0, limit: 20, offset: 0 })

beforeEach(() => {
  window.history.replaceState(null, '', '/')
  mockFetch({
    'GET /ready': () => json({ status: 'ready', checks: { database: { ok: true, detail: 'pgvector 0.8.0' } } }),
    'GET /stats': () =>
      json({ papers: 0, papers_by_source: {}, chunks: 0, pages: 0, jobs_by_state: {}, answers_by_status: {} }),
    'GET /qa': empty,
    'GET /papers': empty,
    'GET /categories': () => json([]),
    'GET /jobs': () => json([]),
  })
})
afterEach(() => vi.unstubAllGlobals())

describe('App shell', () => {
  it('goes from the landing page to the dashboard and between views', async () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Ask your papers.')
    await userEvent.click(screen.getAllByRole('button', { name: 'Open dashboard' })[0])

    expect(window.location.pathname).toBe('/app')
    expect(await screen.findByRole('button', { name: 'Ready' })).toBeInTheDocument()
    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).getByRole('button', { name: 'Home' })).toHaveAttribute('aria-current', 'page')

    await userEvent.click(within(nav).getByRole('button', { name: 'Library' }))
    expect(window.location.pathname).toBe('/app/library')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Library')
    expect(await screen.findByText(/No papers match/)).toBeInTheDocument()

    window.history.back()
    await screen.findByRole('heading', { level: 1, name: 'Home' })
  })

  it('opens Add papers from the landing page and closes it with Escape', async () => {
    render(<App />)
    await userEvent.click(screen.getByRole('button', { name: 'Import from arXiv' }))
    const modal = await screen.findByRole('dialog', { name: 'Add papers' })
    expect(within(modal).getByLabelText('Search arXiv')).toBeInTheDocument()
    await userEvent.click(within(modal).getByRole('button', { name: 'Upload PDF' }))
    expect(within(modal).getByLabelText('PDF file')).toBeVisible()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('sends a question from Home to Ask', async () => {
    vi.unstubAllGlobals()
    const fetch = mockFetch({
      'GET /ready': () => json({ status: 'ready', checks: {} }),
      'GET /stats': () =>
        json({ papers: 1, papers_by_source: {}, chunks: 1, pages: 1, jobs_by_state: {}, answers_by_status: {} }),
      'GET /qa': empty,
      'GET /papers': empty,
      'GET /jobs': () => json([]),
      'POST /qa': () => json({ error: { code: 'dependency_unavailable', message: 'Ollama is not reachable' } }, 503),
    })
    window.history.replaceState(null, '', '/app')
    render(<App />)
    const input = await screen.findByLabelText('Ask a question')
    await userEvent.type(input, 'How many heads?')
    await userEvent.click(within(input.closest('form')!).getByRole('button', { name: 'Ask' }))
    expect(window.location.pathname).toBe('/app/ask')
    expect(await screen.findByRole('alert')).toHaveTextContent('Ollama is not reachable')
    const call = fetch.mock.calls.find((c) => String(c[0]).endsWith('/qa') && c[1]?.method === 'POST')
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ question: 'How many heads?' })
  })
})
