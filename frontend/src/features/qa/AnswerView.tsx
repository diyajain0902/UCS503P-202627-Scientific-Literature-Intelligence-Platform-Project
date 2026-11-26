import { useState } from 'react'
import { formatPages, type QAAnswer, type QAClaim, type QAEvidence } from '../../api/client'
import { seconds } from '../../ui/format'
import { toneForLabel } from '../../ui/tones'
import { SourceCard } from './SourceCard'

function Claim({ claim, selected, onToggle }: { claim: QAClaim; selected: string | null; onToggle: (label: string) => void }) {
  return (
    <li>
      <span className={claim.support === 'unsupported' ? 'claim-unsupported' : undefined}>{claim.text}</span>
      {claim.citations.map((citation) =>
        citation.valid ? (
          <button
            key={citation.label}
            type="button"
            className={`cite tone-${toneForLabel(citation.label)}`}
            aria-pressed={selected === citation.label}
            aria-label={`Show source ${citation.label}`}
            onClick={() => onToggle(citation.label)}
          >
            {citation.label}
          </button>
        ) : (
          <span
            key={citation.label}
            className="cite cite-invalid"
            title="The model cited a passage it was not given; this citation is not valid."
          >
            {citation.label} (invalid)
          </span>
        ),
      )}
      {claim.support === 'unsupported' && <span className="badge-unsupported">Unsupported: no valid citation</span>}
    </li>
  )
}

export function Passages({ evidence }: { evidence: QAEvidence[] }) {
  if (evidence.length === 0) return null
  return (
    <details className="passages">
      <summary>Retrieved passages ({evidence.length})</summary>
      <ol className="passages-list">
        {evidence.map((e) => (
          <li key={e.label} className={`passage-item tone-${toneForLabel(e.label)}`}>
            <div className="passage-head">
              <span className="cite-tag">{e.label}</span>
              <span className="passage-title">{e.paper_title}</span>
              <span className="faint">{formatPages(e.page_start, e.page_end)}</span>
            </div>
            <p className="passage-meta">
              {e.arxiv_id && `arXiv:${e.arxiv_id}v${e.arxiv_version} · `}retrieval rank {e.rank} · score {e.score.toFixed(3)}
              {e.chunk_id === null && ' · source since deleted (snapshot shown)'}
            </p>
            <blockquote className="quote">{e.text}</blockquote>
          </li>
        ))}
      </ol>
    </details>
  )
}

function Verification({ answer }: { answer: QAAnswer }) {
  const invalid = answer.claims.flatMap((c) => c.citations).filter((c) => !c.valid).length
  const unsupported = answer.claims.filter((c) => c.support === 'unsupported').length
  if (invalid === 0 && unsupported === 0) return <span className="verified">✓ All citations verified</span>
  const parts = [
    invalid > 0 && `${invalid} invalid citation${invalid === 1 ? '' : 's'}`,
    unsupported > 0 && `${unsupported} unsupported claim${unsupported === 1 ? '' : 's'}`,
  ].filter(Boolean)
  return <span className="unverified">⚠ {parts.join(' · ')}</span>
}

interface Props {
  answer: QAAnswer
  /** Controlled selection: the parent shows the inspector (Ask). Omit both to show the source inline (History). */
  selected?: string | null
  onSelect?: (label: string | null) => void
}

/** One answer: claims as prose with citation chips, verification footer, and expandable details. */
export function AnswerView({ answer, selected: controlled, onSelect }: Props) {
  const [own, setOwn] = useState<string | null>(null)
  const [showDetails, setShowDetails] = useState(false)
  const selected = onSelect ? (controlled ?? null) : own
  const toggle = (label: string) => {
    const next = selected === label ? null : label
    if (onSelect) onSelect(next)
    else setOwn(next)
  }
  const inline = !onSelect && selected ? answer.evidence.find((e) => e.label === selected) : undefined

  if (answer.status !== 'answered') {
    const declined = answer.status === 'insufficient_evidence'
    return (
      <div className={declined ? 'declined-card' : 'declined-card error-card'}>
        <p role="status" className="declined-msg">
          <span className="dot" aria-hidden="true" />
          <span>
            <b>{declined ? 'Not in your papers.' : 'Could not answer.'}</b>{' '}
            {answer.reason ?? (declined ? "Nothing relevant enough was found, so slip won't guess." : '')}
          </span>
        </p>
        <Passages evidence={answer.evidence} />
      </div>
    )
  }

  return (
    <article className="answer-card" aria-label="Answer">
      <ol className="claims-prose" aria-label="Answer claims">
        {answer.claims.map((claim) => (
          <Claim key={claim.index} claim={claim} selected={selected} onToggle={toggle} />
        ))}
      </ol>
      <div className="answer-foot">
        <Verification answer={answer} />
        <span aria-hidden="true">·</span>
        <span>{seconds(answer.timings.latency_ms)}</span>
        <button type="button" className="btn-text" aria-expanded={showDetails} onClick={() => setShowDetails((s) => !s)}>
          {showDetails ? 'Hide details' : 'Details'}
        </button>
      </div>
      {inline && <SourceCard evidence={inline} variant="inline" onClose={() => setOwn(null)} />}
      {showDetails && (
        <div className="answer-details">
          <p className="meta-line">
            <span>{answer.generation_model ?? 'No model call'}</span>
            <span>prompt {answer.prompt_version}</span>
            {answer.timings.retrieval_ms !== null && <span>retrieval {Math.round(answer.timings.retrieval_ms)} ms</span>}
            {answer.timings.generation_ms !== null && <span>generation {Math.round(answer.timings.generation_ms)} ms</span>}
            <span>{answer.evidence.length} passages</span>
            <span>{answer.embedding_model}</span>
          </p>
          <p className="faint small">
            Citations are checked against the passages retrieved; whether each passage fully supports a claim is not
            verified automatically.
          </p>
          <Passages evidence={answer.evidence} />
        </div>
      )}
    </article>
  )
}
