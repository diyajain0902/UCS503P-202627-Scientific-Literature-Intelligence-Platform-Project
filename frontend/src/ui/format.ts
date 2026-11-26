import type { Paper } from '../api/client'

export function seconds(ms: number): string {
  return `${(ms / 1000).toFixed(1)} s`
}

export function arxivPdfUrl(arxivId: string, version: number | null, page: number): string {
  return `https://arxiv.org/pdf/${arxivId}${version ? `v${version}` : ''}#page=${page}`
}

export function arxivAbsUrl(arxivId: string, version: number | null): string {
  return `https://arxiv.org/abs/${arxivId}${version ? `v${version}` : ''}`
}

/** "A, B, C et al." for long author lists. */
export function shortAuthors(authors: string[], max = 3): string {
  if (authors.length === 0) return ''
  return authors.length > max ? `${authors.slice(0, max).join(', ')} et al.` : authors.join(', ')
}

/** Publication year for arXiv papers; the year added for uploads. */
export function paperYear(paper: Pick<Paper, 'published_at' | 'created_at'>): string {
  return (paper.published_at ?? paper.created_at).slice(0, 4)
}

/** A short name for pills: the part before a colon if that is short, otherwise a truncated title. */
export function shortTitle(title: string, max = 28): string {
  const head = title.split(':')[0].trim()
  if (head.length > 0 && head.length <= max) return head
  return title.length <= max ? title : `${title.slice(0, max - 1).trimEnd()}…`
}
