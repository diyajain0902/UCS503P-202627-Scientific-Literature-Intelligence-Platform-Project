import { useEffect, useRef, useState } from 'react'
import { api, errorMessage, type Page, type Paper, type PaperFilters } from '../../api/client'
import { RecentJobs } from '../ingest/RecentJobs'
import { paperYear, shortAuthors } from '../../ui/format'
import { toneAt } from '../../ui/tones'
import { PaperDrawer } from './PaperDrawer'

const PAGE_SIZE = 24
const FILTER_DELAY_MS = 250
const SOURCES = [
  ['', 'All'],
  ['arxiv', 'arXiv'],
  ['upload', 'Uploads'],
] as const

interface Props {
  refreshKey: number
  onChanged?: () => void
  onAskPaper?: (paper: Paper) => void
  onComparePaper?: (paper: Paper) => void
}

/** Library (FR-16): filterable card grid of papers, the jobs strip, and the paper drawer. */
export function CorpusView({ refreshKey, onChanged, onAskPaper, onComparePaper }: Props) {
  const [draft, setDraft] = useState<Required<PaperFilters>>({ q: '', source: '', category: '', year: '' })
  const [filters, setFilters] = useState<PaperFilters>(draft)
  const applied = useRef(JSON.stringify(draft))
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<Page<Paper> | null>(null)
  const [categories, setCategories] = useState<string[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    api.categories().then(setCategories).catch(() => setCategories([]))
  }, [refreshKey, version])

  // Filters apply as you type, after a short pause.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const next = { ...draft, year: /^\d{4}$/.test(draft.year) ? draft.year : '' }
      if (JSON.stringify(next) === applied.current) return
      applied.current = JSON.stringify(next)
      setOffset(0)
      setFilters(next)
    }, FILTER_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [draft])

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

  const refresh = () => {
    setVersion((v) => v + 1)
    onChanged?.()
  }
  const selectedPaper = page?.items.find((p) => p.id === selected)

  return (
    <div className="view library">
      <div className="toolbar">
        <div className="filter-box">
          <span className="search-glyph" aria-hidden="true" />
          <label htmlFor="filter-q" className="sr-only">
            Filter papers
          </label>
          <input
            id="filter-q"
            placeholder="Filter papers"
            value={draft.q}
            onChange={(e) => setDraft({ ...draft, q: e.target.value })}
            maxLength={200}
          />
        </div>
        <div role="group" aria-label="Source" className="toolbar">
          {SOURCES.map(([value, label]) => (
            <button
              key={label}
              type="button"
              className="pill"
              aria-pressed={draft.source === value}
              onClick={() => setDraft({ ...draft, source: value })}
            >
              {label}
            </button>
          ))}
        </div>
        <label htmlFor="filter-category" className="sr-only">
          Category
        </label>
        <select
          id="filter-category"
          className="pill-select"
          value={draft.category}
          onChange={(e) => setDraft({ ...draft, category: e.target.value })}
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <label htmlFor="filter-year" className="sr-only">
          Year
        </label>
        <input
          id="filter-year"
          className="pill-input"
          inputMode="numeric"
          placeholder="Year"
          maxLength={4}
          value={draft.year}
          onChange={(e) => setDraft({ ...draft, year: e.target.value.replace(/\D/g, '') })}
        />
        {page && <span className="faint small">{page.total} papers</span>}
      </div>

      <RecentJobs refreshKey={refreshKey + version} onChanged={refresh} />

      {error && (
        <p role="alert" className="alert">
          Could not load papers: {error}
        </p>
      )}
      {page && page.items.length === 0 && (
        <p className="empty glass">No papers match. Add some with “+ Add papers”.</p>
      )}
      {page && page.items.length > 0 && (
        <ul className="paper-grid" aria-label="Papers">
          {page.items.map((paper, index) => (
            <li key={paper.id}>
              <button
                type="button"
                className={`paper-card tone-${paper.source === 'upload' ? 'peach' : toneAt(offset + index)}`}
                aria-expanded={selected === paper.id}
                aria-haspopup="dialog"
                onClick={() => setSelected(paper.id)}
              >
                <span className="paper-meta">
                  <span className="dot-sq" aria-hidden="true" />
                  {paperYear(paper)} · {paper.source === 'upload' ? 'Upload' : 'arXiv'}
                </span>
                <span className="paper-title">{paper.title}</span>
                <span className="paper-authors">{shortAuthors(paper.authors) || '—'}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {page && page.total > PAGE_SIZE && (
        <nav className="pager" aria-label="Pagination">
          <button type="button" className="btn btn-light btn-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            Previous
          </button>
          <span>
            {offset + 1}–{Math.min(offset + PAGE_SIZE, page.total)} of {page.total}
          </span>
          <button
            type="button"
            className="btn btn-light btn-sm"
            disabled={offset + PAGE_SIZE >= page.total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </button>
        </nav>
      )}

      {selectedPaper && (
        <PaperDrawer
          key={selectedPaper.id}
          paper={selectedPaper}
          onClose={() => setSelected(null)}
          onDeleted={() => {
            setSelected(null)
            refresh()
          }}
          onAsk={onAskPaper}
          onCompare={onComparePaper}
        />
      )}
    </div>
  )
}
