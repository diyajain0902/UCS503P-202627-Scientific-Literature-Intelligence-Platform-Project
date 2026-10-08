import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { searchResponse } from '../../test/fixtures'
import { json, mockFetch } from '../../test/mockFetch'
import { SearchPanel } from './SearchPanel'

afterEach(() => vi.unstubAllGlobals())

async function search(text: string) {
  await userEvent.type(screen.getByLabelText('Query'), text)
  await userEvent.click(screen.getByRole('button', { name: 'Search' }))
}

describe('SearchPanel', () => {
  it('renders ranked passages with paper, page range, score and source link', async () => {
    const fetch = mockFetch({ 'POST /search': () => json(searchResponse()) })
    render(<SearchPanel />)
    await userEvent.selectOptions(screen.getByLabelText('Results'), '5')
    await search('attention')

    const results = await screen.findByRole('list')
    const item = within(results).getAllByRole('listitem')[0]
    expect(item).toHaveTextContent('Synthetic Paper Title')
    expect(item).toHaveTextContent('pp. 3–4')
    expect(item).toHaveTextContent('score 0.812')
    expect(item).toHaveTextContent('Passage about attention spanning two pages.')
    expect(within(item).getByRole('link')).toHaveAttribute(
      'href',
      'https://arxiv.org/abs/2101.00001v2',
    )
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ query: 'attention', top_k: 5 })
  })

  it('explains an empty result set', async () => {
    mockFetch({ 'POST /search': () => json(searchResponse({ results: [] })) })
    render(<SearchPanel />)
    await search('nothing')
    expect(await screen.findByText(/No passages found/)).toBeInTheDocument()
  })

  it('shows an error when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    render(<SearchPanel />)
    await search('attention')
    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach the backend API')
  })
})
