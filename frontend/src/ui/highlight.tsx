import type { ReactNode } from 'react'

const STOPWORDS = new Set(['what', 'which', 'with', 'that', 'this', 'from', 'does', 'have', 'into', 'about', 'their', 'there'])

/** Query words worth highlighting: four letters or more, not a stopword, de-duplicated. */
export function highlightTerms(query: string): string[] {
  const words = query.toLowerCase().match(/[\p{L}\p{N}][\p{L}\p{N}-]{3,}/gu) ?? []
  return [...new Set(words.filter((w) => !STOPWORDS.has(w)))]
}

/** Wraps case-insensitive matches of the query's terms in <mark>; the text content is unchanged. */
export function highlight(text: string, query: string): ReactNode[] {
  const terms = highlightTerms(query)
  if (terms.length === 0) return [text]
  const pattern = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'giu')
  return text.split(pattern).map((part, i) => (i % 2 === 1 ? <mark key={i}>{part}</mark> : part))
}
