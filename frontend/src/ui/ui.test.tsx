import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { parseRoute, routePath } from '../app/route'
import { parseArxivId } from '../features/ingest/arxivId'
import { jobsNeedingAttention } from '../features/ingest/jobLabels'
import { job } from '../test/fixtures'
import { shortAuthors, shortTitle } from './format'
import { highlight, highlightTerms } from './highlight'
import { dayLabel, groupByDay, timeLabel, whenLabel } from './time'
import { toneForLabel } from './tones'

const now = new Date(2026, 10, 27, 15, 0)
const at = (day: number, hour: number, minute = 0) => new Date(2026, 10, day, hour, minute).toISOString()

describe('time labels', () => {
  it('uses relative times today and the time of day before that', () => {
    expect(timeLabel(at(27, 14, 59), now)).toBe('1 min ago')
    expect(timeLabel(at(27, 15), now)).toBe('just now')
    expect(timeLabel(at(27, 12), now)).toBe('3 h ago')
    expect(timeLabel(at(26, 16, 12), now)).toMatch(/4:12/)
    expect(whenLabel(at(26, 16), now)).toBe('yesterday')
  })

  it('groups items by day in order', () => {
    const items = [at(27, 14), at(27, 9), at(26, 20), at(20, 8)].map((created_at, id) => ({ id, created_at }))
    const groups = groupByDay(items, now)
    expect(groups.map((g) => [g.label, g.items.length])).toEqual([
      ['Today', 2],
      ['Yesterday', 1],
      [dayLabel(at(20, 8), now), 1],
    ])
  })
})

describe('highlight', () => {
  it('picks meaningful query terms', () => {
    expect(highlightTerms('What is scaled dot-product attention?')).toEqual(['scaled', 'dot-product', 'attention'])
  })

  it('marks matches without changing the text', () => {
    const { container } = render(<p>{highlight('Scaled attention, then Attention again.', 'attention')}</p>)
    expect(container).toHaveTextContent('Scaled attention, then Attention again.')
    expect([...container.querySelectorAll('mark')].map((m) => m.textContent)).toEqual(['attention', 'Attention'])
  })

  it('treats regex characters in the query literally', () => {
    const { container } = render(<p>{highlight('cost (approx) applies', 'cost (approx')}</p>)
    expect(container.querySelector('mark')?.textContent).toBe('cost')
  })
})

describe('formatting', () => {
  it('shortens long titles and author lists', () => {
    expect(shortTitle('BERT: Pre-training of Deep Bidirectional Transformers')).toBe('BERT')
    expect(shortTitle('A very long title without any colon in it at all', 20)).toBe('A very long title w…')
    expect(shortAuthors(['A', 'B', 'C', 'D'])).toBe('A, B, C et al.')
    expect(shortAuthors(['A', 'B'])).toBe('A, B')
  })

  it('gives a citation label a stable tone', () => {
    expect(toneForLabel('P1')).toBe('lav')
    expect(toneForLabel('P2')).toBe('mint')
    expect(toneForLabel('P5')).toBe('lav')
  })
})

describe('arXiv IDs', () => {
  it('recognises new- and old-style identifiers and leaves keywords alone', () => {
    expect(parseArxivId('1706.03762')).toBe('1706.03762')
    expect(parseArxivId(' arXiv:1706.03762v7 ')).toBe('1706.03762v7')
    expect(parseArxivId('hep-th/9901001')).toBe('hep-th/9901001')
    expect(parseArxivId('low-rank adaptation')).toBeNull()
  })
})

describe('jobs needing attention', () => {
  it('keeps the newest job per source and drops finished ones', () => {
    const jobs = [
      job({ id: 'a2', source_ref: 'a', state: 'ready', created_at: '2026-10-09T00:00:00Z' }),
      job({ id: 'a1', source_ref: 'a', state: 'failed', created_at: '2026-10-08T00:00:00Z' }),
      job({ id: 'b1', source_ref: 'b', state: 'failed', created_at: '2026-10-08T00:00:00Z' }),
      job({ id: 'c1', source_ref: 'c', state: 'chunking', created_at: '2026-10-10T00:00:00Z' }),
    ]
    expect(jobsNeedingAttention(jobs).map((j) => j.id)).toEqual(['c1', 'b1'])
  })
})

describe('routes', () => {
  it('maps paths to pages and back', () => {
    expect(parseRoute('/')).toEqual({ page: 'landing' })
    expect(parseRoute('/app')).toEqual({ page: 'app', view: 'home' })
    expect(parseRoute('/app/library')).toEqual({ page: 'app', view: 'library' })
    expect(parseRoute('/app/nope')).toEqual({ page: 'app', view: 'home' })
    expect(parseRoute('/elsewhere')).toEqual({ page: 'landing' })
    expect(routePath({ page: 'app', view: 'history' })).toBe('/app/history')
    expect(routePath({ page: 'app', view: 'home' })).toBe('/app')
  })
})
