import { useEffect, useState } from 'react'
import { api, errorMessage, type HistoryItem, type QAAnswer } from '../../api/client'
import { AnswerView } from '../qa/QAPanel'

const STATUS_LABELS: Record<string, string> = {
  answered: 'Answered',
  insufficient_evidence: 'Insufficient evidence',
  error: 'Error',
}

export function HistoryView({ refreshKey }: { refreshKey: number }) {
  const [items, setItems] = useState<HistoryItem[] | null>(null)
  const [answer, setAnswer] = useState<QAAnswer | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .history(50)
      .then((page) => setItems(page.items))
      .catch((err: unknown) => setError(errorMessage(err)))
  }, [refreshKey])

  async function open(id: string) {
    setError(null)
    try {
      setAnswer(await api.answer(id))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <section aria-labelledby="history-heading" className="card">
      <h2 id="history-heading">Question history</h2>
      {error && (
        <p role="alert" className="status-error">
          {error}
        </p>
      )}
      {items && items.length === 0 && <p className="muted">No questions asked yet.</p>}
      {items && items.length > 0 && (
        <ul className="paper-list" aria-label="Past questions">
          {items.map((item) => (
            <li key={item.id}>
              <button type="button" className="link-button" onClick={() => void open(item.id)}>
                {item.question}
              </button>
              <span className="muted small">
                {STATUS_LABELS[item.status] ?? item.status} · {item.claim_count} claims · {Math.round(item.latency_ms)} ms ·{' '}
                {new Date(item.created_at).toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      )}
      {answer && (
        <section aria-label="Saved answer" className="details">
          <h3>{answer.question}</h3>
          {answer.status === 'error' && (
            <p role="status" className="status-error">
              Error: {answer.reason}
            </p>
          )}
          <AnswerView key={answer.id} answer={answer} />
        </section>
      )}
    </section>
  )
}
