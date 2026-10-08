import { useState, type FormEvent } from 'react'
import { api, errorMessage, formatPages, type QAAnswer, type QAEvidence } from '../../api/client'

function EvidenceCard({ evidence, selected }: { evidence: QAEvidence; selected: boolean }) {
  return (
    <article
      id={`evidence-${evidence.label}`}
      className={selected ? 'evidence evidence-selected' : 'evidence'}
      aria-current={selected ? 'true' : undefined}
    >
      <header className="result-header">
        <span className="paper-title">
          [{evidence.label}] {evidence.paper_title}
        </span>
        <span className="muted small">
          {evidence.arxiv_id && `arXiv:${evidence.arxiv_id}v${evidence.arxiv_version} · `}
          {formatPages(evidence.page_start, evidence.page_end)} · retrieval rank {evidence.rank} · score{' '}
          {evidence.score.toFixed(3)}
          {evidence.chunk_id === null && ' · source since deleted (snapshot shown)'}
        </span>
      </header>
      <blockquote className="passage">{evidence.text}</blockquote>
    </article>
  )
}

export function AnswerView({ answer }: { answer: QAAnswer }) {
  const [selected, setSelected] = useState<string | null>(null)
  const evidenceByLabel = new Map(answer.evidence.map((e) => [e.label, e]))
  const selectedEvidence = selected ? evidenceByLabel.get(selected) : undefined

  return (
    <div className="answer">
      {answer.status === 'answered' && (
        <ol className="claims" aria-label="Answer claims">
          {answer.claims.map((claim) => (
            <li key={claim.index}>
              <span>{claim.text}</span>{' '}
              {claim.citations.map((citation) =>
                citation.valid ? (
                  <button
                    key={citation.label}
                    type="button"
                    className="chip"
                    aria-pressed={selected === citation.label}
                    aria-label={`Show source ${citation.label}`}
                    onClick={() => setSelected(citation.label)}
                  >
                    {citation.label}
                  </button>
                ) : (
                  <span
                    key={citation.label}
                    className="chip chip-invalid"
                    title="The model cited a passage it was not given; this citation is not valid."
                  >
                    {citation.label} (invalid)
                  </span>
                ),
              )}
              {claim.support === 'unsupported' && (
                <span className="badge-warning"> Unsupported: no valid citation</span>
              )}
            </li>
          ))}
        </ol>
      )}

      {answer.status === 'insufficient_evidence' && (
        <p role="status" className="notice">
          <strong>Insufficient evidence.</strong> {answer.reason}
        </p>
      )}

      {selectedEvidence && (
        <section aria-label="Citation inspector" className="inspector">
          <h3>Source {selectedEvidence.label}</h3>
          <EvidenceCard evidence={selectedEvidence} selected />
        </section>
      )}

      <p className="muted small">
        {answer.generation_model ? `${answer.generation_model} · ` : 'No model call · '}
        prompt {answer.prompt_version} · {answer.timings.latency_ms} ms
        {answer.status === 'answered' &&
          ' · Citations are checked against the passages retrieved; whether each passage fully supports a claim is not verified automatically.'}
      </p>

      {answer.evidence.length > 0 && (
        <details>
          <summary>Retrieved passages ({answer.evidence.length})</summary>
          {answer.evidence.map((evidence) => (
            <EvidenceCard key={evidence.label} evidence={evidence} selected={selected === evidence.label} />
          ))}
        </details>
      )}
    </div>
  )
}

export function QAPanel() {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<QAAnswer | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError(null)
    setAnswer(null)
    try {
      setAnswer(await api.ask(question))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <section aria-labelledby="qa-heading" className="card">
      <h2 id="qa-heading">Ask the corpus</h2>
      <form onSubmit={submit} className="stack-form">
        <label htmlFor="qa-question">Question</label>
        <textarea
          id="qa-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="e.g. How many attention heads does the base Transformer use?"
          maxLength={1000}
          rows={3}
          required
        />
        <button type="submit" disabled={loading || question.trim() === ''}>
          {loading ? 'Answering… (local model)' : 'Ask'}
        </button>
      </form>
      {error && (
        <p role="alert" className="status-error">
          {error}
        </p>
      )}
      {answer && <AnswerView key={answer.id} answer={answer} />}
    </section>
  )
}
