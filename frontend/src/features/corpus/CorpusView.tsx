import { useEffect, useState, type FormEvent } from 'react'
import { api, errorMessage, type Page, type Paper, type PaperFilters } from '../../api/client'

const PAGE_SIZE = 20

function PaperDetails({ paper, onDeleted }: { paper: Paper; onDeleted: () => void }) {
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  async function remove() {
    setDeleting(true)
    setError(null)
    try {
      await api.deletePaper(paper.id)
      onDeleted()
    } catch (err) {
      setError(errorMessage(err))
      setDeleting(false)
    }
  }

  return (
    <article className="details" aria-label={`Details for ${paper.title}`}>
      <h3>{paper.title}</h3>
      <p className="muted small">
        {paper.source === 'arxiv' && paper.arxiv_id ? (
          <a href={`https://arxiv.org/abs/${paper.arxiv_id}v${paper.arxiv_version}`} target="_blank" rel="noreferrer noopener">
            arXiv:{paper.arxiv_id}v{paper.arxiv_version}
          </a>
        ) : (
          'Uploaded PDF'
        )}
        {paper.published_at && ` · published ${paper.published_at.slice(0, 10)}`} · {paper.page_count ?? '?'} pages ·{' '}
        {paper.chunk_count} chunks · added {new Date(paper.created_at).toLocaleDateString()}
      </p>
      {paper.authors.length > 0 && <p className="small">{paper.authors.join(', ')}</p>}
      {paper.categories.length > 0 && <p className="small muted">Categories: {paper.categories.join(', ')}</p>}
      {paper.abstract && <p className="abstract">{paper.abstract}</p>}
      {!confirming ? (
        <button type="button" className="danger" onClick={() => setConfirming(true)}>
          Delete paper
        </button>
      ) : (
        <div role="group" aria-label="Confirm deletion" className="inline-form">
          <span className="status-error small">
            Delete this paper, its chunks and stored PDF? Past answers keep their quoted passages.
          </span>
          <button type="button" className="danger" disabled={deleting} onClick={() => void remove()}>
            {deleting ? 'Deleting…' : 'Yes, delete'}
          </button>
          <button type="button" className="secondary" onClick={() => setConfirming(false)}>
            Cancel
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="status-error">
          {error}
        </p>
      )}
    </article>
  )
}

export function CorpusView({ refreshKey }: { refreshKey: number }) {
  const [draft, setDraft] = useState<PaperFilters>({ q: '', source: '', category: '', year: '' })
  const [filters, setFilters] = useState<PaperFilters>({})
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<Page<Paper> | null>(null)
  const [categories, setCategories] = useState<string[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    api.categories().then(setCategories).catch(() => setCategories([]))
  }, [refreshKey, version])

  useEffect(() => {
    const controller = new AbortController()
    api
      .corpus(filters, PAGE_SIZE, offset, controller.signal)
      .then((next) => {
        setPage(next)
        setError(null)
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(errorMessage(err))
      })
    return () => controller.abort()
  }, [filters, offset, refreshKey, version])

  function apply(event: FormEvent) {
    event.preventDefault()
    setOffset(0)
    setSelected(null)
    setFilters({ ...draft })
  }

  const selectedPaper = page?.items.find((p) => p.id === selected)

  return (
    <section aria-labelledby="corpus-heading" className="card">
      <h2 id="corpus-heading">
        Corpus{page && <span className="muted"> ({page.total})</span>}
      </h2>
      <form onSubmit={apply} className="inline-form" aria-label="Filter papers">
        <label htmlFor="filter-q">Title</label>
        <input id="filter-q" value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} maxLength={200} />
        <label htmlFor="filter-source">Source</label>
        <select
          id="filter-source"
          value={draft.source}
          onChange={(e) => setDraft({ ...draft, source: e.target.value as PaperFilters['source'] })}
        >
          <option value="">Any</option>
          <option value="arxiv">arXiv</option>
          <option value="upload">Upload</option>
        </select>
        <label htmlFor="filter-category">Category</label>
        <select id="filter-category" value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })}>
          <option value="">Any</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <label htmlFor="filter-year">Year</label>
        <input
          id="filter-year"
          inputMode="numeric"
          pattern="[0-9]{4}"
          value={draft.year}
          onChange={(e) => setDraft({ ...draft, year: e.target.value })}
          className="narrow"
        />
        <button type="submit">Apply</button>
      </form>
      {error && (
        <p role="alert" className="status-error">
          Could not load papers: {error}
        </p>
      )}
      {page && page.items.length === 0 && <p className="muted">No papers match. Add some under “Add papers”.</p>}
      {page && page.items.length > 0 && (
        <ul className="paper-list" aria-label="Papers">
          {page.items.map((paper) => (
            <li key={paper.id}>
              <button
                type="button"
                className="link-button"
                aria-expanded={selected === paper.id}
                onClick={() => setSelected(selected === paper.id ? null : paper.id)}
              >
                {paper.title}
              </button>
              <span className="muted small">
                {paper.arxiv_id ? `arXiv:${paper.arxiv_id}v${paper.arxiv_version}` : 'Upload'} · {paper.page_count ?? '?'} pages ·{' '}
                {paper.chunk_count} chunks
              </span>
              {selected === paper.id && selectedPaper && (
                <PaperDetails
                  paper={selectedPaper}
                  onDeleted={() => {
                    setSelected(null)
                    setVersion((v) => v + 1)
                  }}
                />
              )}
            </li>
          ))}
        </ul>
      )}
      {page && page.total > PAGE_SIZE && (
        <nav className="inline-form" aria-label="Pagination">
          <button type="button" className="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            Previous
          </button>
          <span className="muted small">
            {offset + 1}–{Math.min(offset + PAGE_SIZE, page.total)} of {page.total}
          </span>
          <button
            type="button"
            className="secondary"
            disabled={offset + PAGE_SIZE >= page.total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </button>
        </nav>
      )}
    </section>
  )
}
