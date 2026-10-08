import { useState, type FormEvent } from 'react'
import { api, errorMessage, formatPages, type SearchResponse } from '../../api/client'

const TOP_K_OPTIONS = [5, 10, 20]

export function SearchPanel() {
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
    <section aria-labelledby="search-heading" className="card">
      <h2 id="search-heading">Semantic search</h2>
      <form onSubmit={submit} className="inline-form" role="search">
        <label htmlFor="search-query">Query</label>
        <input
          id="search-query"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="e.g. how does multi-head attention work?"
          maxLength={1000}
          required
        />
        <label htmlFor="search-top-k">Results</label>
        <select id="search-top-k" value={topK} onChange={(event) => setTopK(Number(event.target.value))}>
          {TOP_K_OPTIONS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
        <button type="submit" disabled={loading || query.trim() === ''}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {error && (
        <p role="alert" className="status-error">
          {error}
        </p>
      )}
      {response && (
        <>
          <p className="muted small" role="status">
            {response.results.length} passages · {response.embedding_model} · {response.took_ms} ms
          </p>
          {response.results.length === 0 && <p className="muted">No passages found. Is the corpus empty?</p>}
          <ol className="results">
            {response.results.map((hit) => (
              <li key={hit.chunk_id}>
                <article>
                  <header className="result-header">
                    <span className="paper-title">{hit.paper.title}</span>
                    <span className="muted small">
                      {hit.paper.arxiv_id && (
                        <a
                          href={`https://arxiv.org/abs/${hit.paper.arxiv_id}v${hit.paper.arxiv_version}`}
                          target="_blank"
                          rel="noreferrer noopener"
                        >
                          arXiv:{hit.paper.arxiv_id}v{hit.paper.arxiv_version}
                        </a>
                      )}
                      {' · '}
                      {formatPages(hit.page_start, hit.page_end)} · score {hit.score.toFixed(3)}
                    </span>
                  </header>
                  <blockquote className="passage">{hit.text}</blockquote>
                </article>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  )
}
