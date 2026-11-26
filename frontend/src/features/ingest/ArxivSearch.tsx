import { useState, type FormEvent } from 'react'
import { api, errorMessage, type ArxivResult, type Job } from '../../api/client'
import { shortAuthors } from '../../ui/format'
import { parseArxivId } from './arxivId'
import { JobStatus } from './JobStatus'

interface Props {
  onImported: () => void
  pollIntervalMs?: number
  autoFocus?: boolean
}

/** arXiv tab of "Add papers": one input that searches by keyword (FR-01) or imports an ID directly (FR-02). */
export function ArxivSearch({ onImported, pollIntervalMs = 1000, autoFocus = false }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<ArxivResult[] | null>(null)
  const [jobs, setJobs] = useState<Record<string, Job>>({})
  const [direct, setDirect] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const id = parseArxivId(query)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      if (id) {
        setDirect(await api.importArxiv(id))
      } else {
        setResults(await api.searchArxiv(query))
      }
    } catch (err) {
      if (!id) setResults(null)
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  async function importPaper(result: ArxivResult) {
    setError(null)
    try {
      const job = await api.importArxiv(`${result.arxiv_id}v${result.version}`)
      setJobs((current) => ({ ...current, [result.arxiv_id]: job }))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <div className="stack">
      <form onSubmit={submit} className="stack" role="search">
        <div className="field">
          <span className="search-glyph" aria-hidden="true" />
          <label htmlFor="arxiv-query" className="sr-only">
            Search arXiv
          </label>
          <input
            id="arxiv-query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. low-rank adaptation"
            maxLength={200}
            autoComplete="off"
            autoFocus={autoFocus}
            required
          />
          <button type="submit" className="btn btn-dark btn-pill btn-sm" disabled={loading || query.trim() === ''}>
            {loading ? (id ? 'Adding…' : 'Searching…') : id ? 'Import' : 'Search'}
          </button>
        </div>
        <p className="faint small">Search by keyword or paste an ID like 1706.03762</p>
      </form>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {direct && (
        <JobStatus key={direct.id} job={direct} pollIntervalMs={pollIntervalMs} onFinished={(d) => d.state === 'ready' && onImported()} />
      )}
      {results && results.length === 0 && <p className="empty">No arXiv results.</p>}
      {results && results.length > 0 && (
        <ul className="arxiv-results" aria-label="arXiv results">
          {results.map((result) => {
            const job = jobs[result.arxiv_id]
            const current = result.stored_version === result.version
            return (
              <li key={result.arxiv_id} className="arxiv-row">
                <div className="arxiv-row-text">
                  <div className="arxiv-row-title" title={result.title}>
                    {result.title}
                  </div>
                  <div className="arxiv-row-meta">
                    {shortAuthors(result.authors, 2)}
                    {result.published_at && ` · ${result.published_at.slice(0, 4)}`} · arXiv:{result.arxiv_id}v{result.version}
                  </div>
                </div>
                {job ? (
                  <JobStatus
                    job={job}
                    showName={false}
                    pollIntervalMs={pollIntervalMs}
                    onFinished={(d) => d.state === 'ready' && onImported()}
                  />
                ) : current ? (
                  <span className="added" title={`In your library as v${result.stored_version}`}>
                    Added ✓
                  </span>
                ) : (
                  <button type="button" className="btn btn-dark btn-pill btn-sm" onClick={() => void importPaper(result)}>
                    {result.stored_version ? `Update to v${result.version}` : 'Add'}
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
