import { Fragment, useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { api, errorMessage, type QAAnswer } from '../../api/client'
import { useEscape } from '../../ui/hooks'
import { AnswerView } from './AnswerView'
import { SourceCard } from './SourceCard'

/** A question handed to the Ask view from elsewhere (Home, a paper drawer). `send` asks it straight away. */
export interface AskRequest {
  id: number
  question: string
  send: boolean
}

interface Turn {
  key: number
  question: string
  answer: QAAnswer | null
  error: string | null
}

/** Grounded Q&A as a thread (FR-09–FR-11). Each question is answered independently by the backend. */
export function QAPanel({ toolbar, request }: { toolbar?: ReactNode; request?: AskRequest | null }) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [draft, setDraft] = useState('')
  const [selected, setSelected] = useState<{ turn: number; label: string } | null>(null)
  const nextKey = useRef(0)
  const handled = useRef<number | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const end = useRef<HTMLDivElement>(null)
  const loading = turns.some((t) => !t.answer && !t.error)
  useEscape(selected !== null, () => setSelected(null))

  const ask = useCallback(async (text: string) => {
    const question = text.trim()
    if (!question) return
    const key = nextKey.current++
    setTurns((current) => [...current, { key, question, answer: null, error: null }])
    try {
      const answer = await api.ask(question)
      setTurns((current) => current.map((t) => (t.key === key ? { ...t, answer } : t)))
    } catch (err) {
      setTurns((current) => current.map((t) => (t.key === key ? { ...t, error: errorMessage(err) } : t)))
    }
  }, [])

  const [prefilled, setPrefilled] = useState<number | null>(null)
  if (request && !request.send && request.id !== prefilled) {
    setPrefilled(request.id)
    setDraft(request.question)
  }

  useEffect(() => {
    if (!request || handled.current === request.id) return
    handled.current = request.id
    if (request.send) void ask(request.question)
    else input.current?.focus()
  }, [request, ask])

  useEffect(() => {
    end.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [turns.length])

  function submit(event: FormEvent) {
    event.preventDefault()
    if (loading) return
    const question = draft
    setDraft('')
    void ask(question)
  }

  const selectedTurn = selected ? turns.find((t) => t.key === selected.turn) : undefined
  const evidence = selectedTurn?.answer?.evidence.find((e) => e.label === selected?.label)

  return (
    <div className="ask-layout">
      <div className="ask-column">
        {toolbar}
        {turns.length === 0 && (
          <div className="ask-empty">
            <strong>Ask your papers.</strong>
            Every claim cites the exact passage and page. When your papers don't cover it, slip says so instead of
            guessing.
          </div>
        )}
        <div className="thread">
          {turns.map((turn) => (
            <Fragment key={turn.key}>
              <div className="bubble">{turn.question}</div>
              {turn.answer ? (
                <AnswerView
                  answer={turn.answer}
                  selected={selected?.turn === turn.key ? selected.label : null}
                  onSelect={(label) => setSelected(label ? { turn: turn.key, label } : null)}
                />
              ) : turn.error ? (
                <p role="alert" className="alert">
                  {turn.error}
                </p>
              ) : (
                <p className="pending" aria-live="polite">
                  <span className="dot dot-pulse tone-mint" aria-hidden="true" />
                  Answering… (local model)
                </p>
              )}
            </Fragment>
          ))}
          <div ref={end} />
        </div>
        <form className="composer" onSubmit={submit}>
          <label htmlFor="qa-question" className="sr-only">
            Question
          </label>
          <input
            id="qa-question"
            ref={input}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={turns.length ? 'Ask another question…' : 'Ask a question about your papers…'}
            maxLength={1000}
            autoComplete="off"
          />
          <button type="submit" className="btn btn-dark" disabled={loading || draft.trim() === ''}>
            Ask
          </button>
        </form>
      </div>
      {evidence && <SourceCard evidence={evidence} onClose={() => setSelected(null)} />}
    </div>
  )
}
