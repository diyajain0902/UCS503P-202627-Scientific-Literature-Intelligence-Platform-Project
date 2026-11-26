import { formatPages } from '../../api/client'
import { arxivPdfUrl } from '../../ui/format'
import { CloseButton } from '../../ui/overlay'
import { toneForLabel } from '../../ui/tones'

/** The fields shared by Q&A evidence and analysis evidence. */
export interface SourceLike {
  label: string
  paper_title: string
  arxiv_id: string | null
  arxiv_version: number | null
  page_start: number
  page_end: number
  score: number
  text: string
  chunk_id: string | null
  rank?: number
}

/** Citation inspector: the exact passage behind a citation chip, with its provenance. */
export function SourceCard({
  evidence,
  onClose,
  variant = 'inspector',
}: {
  evidence: SourceLike
  onClose: () => void
  variant?: 'inspector' | 'inline'
}) {
  const className = variant === 'inspector' ? 'inspector glass-strong' : 'inline-source'
  return (
    <section aria-label="Citation inspector" className={`${className} tone-${toneForLabel(evidence.label)}`}>
      <div className="panel-head">
        <span className="cite-tag">{evidence.label}</span>
        <span className="faint small">{formatPages(evidence.page_start, evidence.page_end)}</span>
        <CloseButton onClick={onClose} label="Close source" />
      </div>
      <h3 className="inspector-title">{evidence.paper_title}</h3>
      <p className="passage-meta">
        {evidence.arxiv_id && `arXiv:${evidence.arxiv_id}v${evidence.arxiv_version} · `}
        {evidence.rank !== undefined && `rank ${evidence.rank} · `}
        score {evidence.score.toFixed(3)}
        {evidence.chunk_id === null && ' · source since deleted (snapshot shown)'}
      </p>
      <blockquote className="quote">“{evidence.text}”</blockquote>
      {evidence.arxiv_id && (
        <a
          className="btn btn-light btn-sm source-open"
          href={arxivPdfUrl(evidence.arxiv_id, evidence.arxiv_version, evidence.page_start)}
          target="_blank"
          rel="noreferrer noopener"
        >
          Open PDF at p. {evidence.page_start}
        </a>
      )}
    </section>
  )
}
