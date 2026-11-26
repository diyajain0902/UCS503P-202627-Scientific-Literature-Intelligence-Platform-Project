import { useCallback, useEffect, useState } from 'react'
import { api, errorMessage, type HistoryItem, type QAAnswer } from '../../api/client'
import { AnswerView } from '../qa/AnswerView'
import { seconds } from '../../ui/format'
import { CloseButton, Overlay } from '../../ui/overlay'
import { groupByDay, timeLabel } from '../../ui/time'
import { OUTCOME_LABELS, outcomeTone } from '../../ui/tones'

/** Question history (FR-18), grouped by day; a row opens the saved answer in a drawer. */
export function HistoryView({ refreshKey, openId }: { refreshKey: number; openId?: string | null }) {
  const [items, setItems] = useState<HistoryItem[] | null>(null)
  const [answer, setAnswer] = useState<QAAnswer | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .history(50)
      .then((page) => setItems(page.items))
      .catch((err: unknown) => setError(errorMessage(err)))
  }, [refreshKey])

  const open = useCallback(async (id: string) => {
    setError(null)
    try {
      setAnswer(await api.answer(id))
    } catch (err) {
      setError(errorMessage(err))
    }
  }, [])

  useEffect(() => {
    if (!openId) return
    api
      .answer(openId)
      .then(setAnswer)
      .catch((err: unknown) => setError(errorMessage(err)))
  }, [openId])

  return (
    <div className="view narrow">
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {items && items.length === 0 && <p className="empty glass">No questions asked yet.</p>}
      {items &&
        groupByDay(items).map((group) => (
          <section key={group.label} aria-labelledby={`day-${group.label}`}>
            <h2 id={`day-${group.label}`} className="group-label">
              {group.label}
            </h2>
            <ul className="row-list glass">
              {group.items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className="row"
                    aria-pressed={answer?.id === item.id}
                    title={`${OUTCOME_LABELS[item.status] ?? item.status} · ${item.claim_count} claims · ${seconds(item.latency_ms)}`}
                    onClick={() => void open(item.id)}
                  >
                    <span className={`dot tone-${outcomeTone(item.status)}`} aria-hidden="true" />
                    <span className="row-text">{item.question}</span>
                    <span className="sr-only">{OUTCOME_LABELS[item.status] ?? item.status}</span>
                    <span className="row-when">{timeLabel(item.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      {answer && (
        <Overlay kind="drawer" label="Saved answer" onClose={() => setAnswer(null)}>
          <div className="panel-head">
            <span className="faint small">{new Date(answer.created_at).toLocaleString()}</span>
            <CloseButton onClick={() => setAnswer(null)} />
          </div>
          <section aria-label="Saved answer" className="thread">
            <div className="bubble">{answer.question}</div>
            <AnswerView key={answer.id} answer={answer} />
          </section>
        </Overlay>
      )}
    </div>
  )
}
