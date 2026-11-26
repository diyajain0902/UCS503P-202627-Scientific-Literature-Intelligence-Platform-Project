import { useState, type FormEvent, type ReactNode } from 'react'
import { api, errorMessage, formatPages, type SearchResponse } from '../../api/client'
import { arxivAbsUrl } from '../../ui/format'
import { highlight } from '../../ui/highlight'

const TOP_K_OPTIONS = [5, 10, 20]

/** "Find passages": semantic search with page provenance (FR-08), no answer generation. */
export function SearchPanel({ toolbar }: { toolbar?: ReactNode }) {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(10)
  const [response, setResponse] = useState<SearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      setResponse(await api.search(query, topK))
    } catch (err) {
      setResponse(null)
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="ask-layout">
      <div className="ask-column">
        {toolbar}
        {!response && !error && (
          <div className="ask-empty">
            <strong>Find passages.</strong>
            Search every indexed page by meaning and keywords. Results show the paper, pages and score; nothing is
            generated.
          </div>
        )}
        {error && (
          <p role="alert" className="alert">
            {error}
          </p>
        )}
        {response && (
          <>
            <p className="caption" role="status">
              {response.results.length} passages matching <b>“{response.query}”</b> · {response.embedding_model} ·{' '}
              {response.took_ms} ms
            </p>
            {response.results.length === 0 && <p className="empty glass">No passages found. Is the library empty?</p>}
            <ol className="hits" aria-label="Passages">
              {response.results.map((hit) => (
                <li key={hit.chunk_id}>
                  <article className="hit glass">
                    <header className="hit-head">
                      <span className="hit-title">{hit.paper.title}</span>
                      <span className="row-when">{formatPages(hit.page_start, hit.page_end)}</span>
                    </header>
                    <p className="hit-text">{highlight(hit.text, response.query)}</p>
                    <p className="hit-meta">
                      {hit.paper.arxiv_id && (
                        <a href={arxivAbsUrl(hit.paper.arxiv_id, hit.paper.arxiv_version)} target="_blank" rel="noreferrer noopener">
                          arXiv:{hit.paper.arxiv_id}v{hit.paper.arxiv_version}
                        </a>
                      )}
                      <span>rank {hit.rank}</span>
                      <span>score {hit.score.toFixed(3)}</span>
                      {hit.rank_score !== null && <span>rerank {hit.rank_score.toFixed(2)}</span>}
                    </p>
                  </article>
                </li>
              ))}
            </ol>
          </>
        )}
        <form onSubmit={submit} className="composer" role="search">
          <label htmlFor="search-query" className="sr-only">
            Query
          </label>
          <input
            id="search-query"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search passages…"
            maxLength={1000}
            required
          />
          <label htmlFor="search-top-k" className="sr-only">
            Results
          </label>
          <select id="search-top-k" value={topK} onChange={(event) => setTopK(Number(event.target.value))}>
            {TOP_K_OPTIONS.map((k) => (
              <option key={k} value={k}>
                {k} results
              </option>
            ))}
          </select>
          <button type="submit" className="btn btn-dark" disabled={loading || query.trim() === ''}>
            {loading ? 'Searching…' : 'Search'}
          </button>
        </form>
      </div>
    </div>
  )
}
