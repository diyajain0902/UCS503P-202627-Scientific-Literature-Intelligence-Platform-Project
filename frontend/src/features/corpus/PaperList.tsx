import { useEffect, useState } from 'react'
import { api, errorMessage, type Page, type Paper } from '../../api/client'

type State =
  | { kind: 'loading' }
  | { kind: 'loaded'; page: Page<Paper> }
  | { kind: 'error'; message: string }

export function PaperList({ refreshKey }: { refreshKey: number }) {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    api
      .papers(50, 0, controller.signal)
      .then((page) => setState({ kind: 'loaded', page }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setState({ kind: 'error', message: errorMessage(error) })
      })
    return () => controller.abort()
  }, [refreshKey])

  return (
    <section aria-labelledby="corpus-heading" className="card">
      <h2 id="corpus-heading">
        Corpus{state.kind === 'loaded' && <span className="muted"> ({state.page.total})</span>}
      </h2>
      {state.kind === 'loading' && <p className="muted">Loading papers…</p>}
      {state.kind === 'error' && (
        <p role="alert" className="status-error">
          Could not load papers: {state.message}
        </p>
      )}
      {state.kind === 'loaded' && state.page.items.length === 0 && (
        <p className="muted">No papers yet. Import one from arXiv to get started.</p>
      )}
      {state.kind === 'loaded' && state.page.items.length > 0 && (
        <ul className="paper-list">
          {state.page.items.map((paper) => (
            <li key={paper.id}>
              <span className="paper-title">{paper.title}</span>
              <span className="muted small">
                {paper.arxiv_id && `arXiv:${paper.arxiv_id}v${paper.arxiv_version} · `}
                {paper.authors.slice(0, 3).join(', ')}
                {paper.authors.length > 3 && ' et al.'}
                {` · ${paper.page_count ?? '?'} pages · ${paper.chunk_count} chunks`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
