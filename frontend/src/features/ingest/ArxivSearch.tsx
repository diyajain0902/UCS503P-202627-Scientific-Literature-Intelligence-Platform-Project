import { useState, type FormEvent } from 'react'
import { api, errorMessage, type ArxivResult, type Job } from '../../api/client'
import { JobStatus } from './JobStatus'

interface Props {
  onImported: () => void
  pollIntervalMs?: number
}

export function ArxivSearch({ onImported, pollIntervalMs = 1000 }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<ArxivResult[] | null>(null)
  const [jobs, setJobs] = useState<Record<string, Job>>({})
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function search(event: FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      setResults(await api.searchArxiv(query))
    } catch (err) {
      setResults(null)
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
    <section aria-labelledby="arxiv-search-heading" className="card">
      <h2 id="arxiv-search-heading">Find papers on arXiv</h2>
      <form onSubmit={search} className="inline-form" role="search">
        <label htmlFor="arxiv-query">Keywords</label>
        <input
          id="arxiv-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="e.g. dense passage retrieval"
          maxLength={200}
          required
        />
        <button type="submit" disabled={loading || query.trim() === ''}>
          {loading ? 'Searching…' : 'Search arXiv'}
        </button>
      </form>
      {error && (
        <p role="alert" className="status-error">
          {error}
        </p>
      )}
      {results && results.length === 0 && <p className="muted">No arXiv results.</p>}
      {results && results.length > 0 && (
        <ul className="paper-list" aria-label="arXiv results">
          {results.map((result) => {
            const job = jobs[result.arxiv_id]
            const current = result.stored_version === result.version
            return (
              <li key={result.arxiv_id}>
                <span className="paper-title">{result.title}</span>
                <span className="muted small">
                  arXiv:{result.arxiv_id}v{result.version} · {result.authors.slice(0, 3).join(', ')}
                  {result.authors.length > 3 && ' et al.'}
                  {result.published_at && ` · ${result.published_at.slice(0, 4)}`}
                </span>
                {job ? (
                  <JobStatus job={job} pollIntervalMs={pollIntervalMs} onFinished={(d) => d.state === 'ready' && onImported()} />
                ) : current ? (
                  <span className="status-ok small">In corpus (v{result.stored_version})</span>
                ) : (
                  <span>
                    <button type="button" onClick={() => void importPaper(result)}>
                      {result.stored_version ? `Update to v${result.version}` : 'Import'}
                    </button>
                  </span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
