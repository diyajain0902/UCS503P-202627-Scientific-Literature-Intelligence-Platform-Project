import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, errorMessage, TERMINAL_STATES, type HistoryItem, type Job, type Paper, type Stats } from '../../api/client'
import { jobName, STATE_LABELS } from '../ingest/jobLabels'
import { shortTitle } from '../../ui/format'
import { whenLabel } from '../../ui/time'
import { OUTCOME_LABELS, outcomeTone } from '../../ui/tones'

interface Props {
  refreshKey: number
  onAsk: (question: string) => void
  onOpenAnswer: (id: string) => void
  onNavigate: (view: 'library' | 'history') => void
  onAddPapers: () => void
  pollIntervalMs?: number
}

interface Data {
  stats: Stats
  recent: HistoryItem[]
  papers: Paper[]
  active: Job[]
}

/** Home (FR-22): ask box, suggestions from the newest papers, indexing banner, recent questions, one stats line. */
export function HomeView({ refreshKey, onAsk, onOpenAnswer, onNavigate, onAddPapers, pollIntervalMs = 3000 }: Props) {
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [question, setQuestion] = useState('')

  const load = useCallback(() => {
    Promise.all([api.stats(), api.history(3), api.papers(3), api.jobs(20)])
      .then(([stats, history, papers, jobs]) => {
        setData({
          stats,
          recent: history.items,
          papers: papers.items,
          active: jobs.filter((job) => !TERMINAL_STATES.has(job.state)),
        })
        setError(null)
      })
      .catch((err: unknown) => setError(errorMessage(err)))
  }, [])

  useEffect(load, [load, refreshKey])

  const indexing = (data?.active.length ?? 0) > 0
  useEffect(() => {
    if (!indexing) return
    const timer = window.setInterval(load, pollIntervalMs)
    return () => window.clearInterval(timer)
  }, [indexing, load, pollIntervalMs])

  function submit(event: FormEvent) {
    event.preventDefault()
    if (question.trim()) onAsk(question.trim())
  }

  if (error)
    return (
      <p role="alert" className="alert">
        Could not load the dashboard: {error}
      </p>
    )

  const paperCount = data?.stats.papers ?? 0
  const answers = Object.values(data?.stats.answers_by_status ?? {}).reduce((a, b) => a + b, 0)
  const first = data?.active[0]
  const activeCount = data?.active.length ?? 0

  return (
    <div className="view home">
      <div className="home-hero">
        <h2 className="home-headline">
          What do you want to <span className="serif">know?</span>
        </h2>
        <form className="askbox" onSubmit={submit}>
          <div className="askbox-inner">
            <label htmlFor="home-question" className="sr-only">
              Ask a question
            </label>
            <input
              id="home-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder={data ? `Ask anything about your ${paperCount} papers…` : 'Ask anything about your papers…'}
              maxLength={1000}
              autoComplete="off"
            />
            <button type="submit" className="btn btn-dark" disabled={question.trim() === ''}>
              Ask
            </button>
          </div>
        </form>
        {data && data.papers.length > 0 && (
          <div className="suggestions" aria-label="Suggested questions">
            {data.papers.map((paper) => {
              const suggestion = `What is the main contribution of ${shortTitle(paper.title, 60)}?`
              return (
                <button key={paper.id} type="button" className="suggestion" title={suggestion} onClick={() => onAsk(suggestion)}>
                  {suggestion}
                </button>
              )
            })}
          </div>
        )}
        {data && paperCount === 0 && (
          <div className="suggestions">
            <button type="button" className="btn btn-dark btn-pill" onClick={onAddPapers}>
              + Add your first papers
            </button>
          </div>
        )}
      </div>

      {first && (
        <button type="button" className="index-banner glass" onClick={() => onNavigate('library')}>
          <span className="dot dot-pulse tone-lav" aria-hidden="true" />
          <span className="index-banner-text">
            Indexing{' '}
            <b>
              {activeCount} paper{activeCount === 1 ? '' : 's'}
            </b>{' '}
            — {jobName(first)}: {STATE_LABELS[first.state] ?? first.state}
          </span>
          <span className="faint small">View</span>
        </button>
      )}

      <section aria-labelledby="recent-heading">
        <div className="section-head">
          <h3 id="recent-heading">Recent</h3>
          <button type="button" className="btn-text" onClick={() => onNavigate('history')}>
            See all
          </button>
        </div>
        {data && data.recent.length === 0 && <p className="empty glass">No questions yet. Ask one above.</p>}
        {data && data.recent.length > 0 && (
          <ul className="row-list glass" aria-label="Recent questions">
            {data.recent.map((item) => (
              <li key={item.id}>
                <button type="button" className="row" onClick={() => onOpenAnswer(item.id)}>
                  <span className={`dot tone-${outcomeTone(item.status)}`} aria-hidden="true" />
                  <span className="row-text">{item.question}</span>
                  <span className="sr-only">{OUTCOME_LABELS[item.status] ?? item.status}</span>
                  <span className="row-when">{whenLabel(item.created_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {data ? (
        <p className="stats-line" aria-label="Library statistics">
          <span>
            <b>{data.stats.papers.toLocaleString()}</b> papers
          </span>
          <span>
            <b>{data.stats.chunks.toLocaleString()}</b> passages
          </span>
          <span>
            <b>{answers.toLocaleString()}</b> answers
          </span>
        </p>
      ) : (
        <p className="stats-line" aria-live="polite">
          Loading…
        </p>
      )}
    </div>
  )
}
