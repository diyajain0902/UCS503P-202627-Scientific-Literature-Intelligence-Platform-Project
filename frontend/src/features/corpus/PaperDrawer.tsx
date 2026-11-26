import { useState } from 'react'
import { api, errorMessage, type Paper } from '../../api/client'
import { PaperAnalysis } from '../analysis/PaperAnalysis'
import { arxivAbsUrl, paperYear } from '../../ui/format'
import { CloseButton, Overlay } from '../../ui/overlay'

interface Props {
  paper: Paper
  onClose: () => void
  onDeleted: () => void
  onAsk?: (paper: Paper) => void
  onCompare?: (paper: Paper) => void
}

/** Paper details drawer: abstract, Ask / Summarise / Compare, extraction, and a two-step delete (FR-16). */
export function PaperDrawer({ paper, onClose, onDeleted, onAsk, onCompare }: Props) {
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
    <Overlay kind="drawer" label={`Details for ${paper.title}`} onClose={onClose}>
      <div className="panel-head">
        <span className="faint small">
          {paper.source === 'arxiv' && paper.arxiv_id ? (
            <a href={arxivAbsUrl(paper.arxiv_id, paper.arxiv_version)} target="_blank" rel="noreferrer noopener">
              arXiv:{paper.arxiv_id}v{paper.arxiv_version}
            </a>
          ) : (
            'Uploaded PDF'
          )}{' '}
          · {paperYear(paper)}
        </span>
        <CloseButton onClick={onClose} />
      </div>
      <div>
        <h2 className="drawer-title">{paper.title}</h2>
        {paper.authors.length > 0 && <p className="drawer-authors">{paper.authors.join(', ')}</p>}
      </div>
      {paper.categories.length > 0 && (
        <p className="tags" aria-label="Categories">
          {paper.categories.map((c) => (
            <span key={c} className="tag">
              {c}
            </span>
          ))}
        </p>
      )}
      {paper.abstract ? <p className="drawer-abstract">{paper.abstract}</p> : <p className="faint small">No abstract stored.</p>}
      <PaperAnalysis
        paperId={paper.id}
        leading={
          onAsk && (
            <button type="button" className="btn btn-dark btn-grow" onClick={() => onAsk(paper)}>
              Ask this paper
            </button>
          )
        }
        trailing={
          onCompare && (
            <button type="button" className="btn btn-light btn-grow" onClick={() => onCompare(paper)}>
              Compare
            </button>
          )
        }
      />
      <div className="drawer-foot">
        <span>
          {paper.page_count ?? '?'} pages · {paper.chunk_count} passages · added {new Date(paper.created_at).toLocaleDateString()}
        </span>
        {!confirming ? (
          <button type="button" className="btn-text btn-danger-text" aria-label="Delete paper" onClick={() => setConfirming(true)}>
            Delete
          </button>
        ) : (
          <div role="group" aria-label="Confirm deletion" className="confirm">
            <span>Delete this paper, its passages and stored PDF? Past answers keep their quoted passages.</span>
            <span className="confirm-actions">
              <button type="button" className="btn btn-danger btn-sm" disabled={deleting} onClick={() => void remove()}>
                {deleting ? 'Deleting…' : 'Yes, delete'}
              </button>
              <button type="button" className="btn btn-light btn-sm" onClick={() => setConfirming(false)}>
                Cancel
              </button>
            </span>
          </div>
        )}
        {error && (
          <p role="alert" className="alert">
            {error}
          </p>
        )}
      </div>
    </Overlay>
  )
}
