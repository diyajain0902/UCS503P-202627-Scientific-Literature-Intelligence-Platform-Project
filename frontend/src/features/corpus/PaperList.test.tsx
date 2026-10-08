import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { paper } from '../../test/fixtures'
import { json, mockFetch } from '../../test/mockFetch'
import { PaperList } from './PaperList'

afterEach(() => vi.unstubAllGlobals())

describe('PaperList', () => {
  it('lists papers with provenance details', async () => {
    mockFetch({ 'GET /papers': () => json({ items: [paper()], total: 1, limit: 50, offset: 0 }) })
    render(<PaperList refreshKey={0} />)
    expect(await screen.findByText('Synthetic Paper Title')).toBeInTheDocument()
    const details = screen.getByText(/arXiv:2101.00001v2/)
    expect(details).toHaveTextContent('A. One, B. Two, C. Three et al.')
    expect(details).toHaveTextContent('12 pages · 40 chunks')
  })

  it('shows an empty state', async () => {
    mockFetch({ 'GET /papers': () => json({ items: [], total: 0, limit: 50, offset: 0 }) })
    render(<PaperList refreshKey={0} />)
    expect(await screen.findByText(/No papers yet/)).toBeInTheDocument()
  })
})
