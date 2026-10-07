import { useEffect, useState, type FormEvent } from 'react'
import { api, errorMessage, TERMINAL_STATES, type Job } from '../../api/client'

const STATE_LABELS: Record<string, string> = {
  queued: 'Queued',
  fetching: 'Fetching from arXiv',
  extracting: 'Extracting text',
  chunking: 'Chunking',
  embedding: 'Computing embeddings',
  ready: 'Ready',
  failed: 'Failed',
}

interface Props {
  onImported: () => void
  pollIntervalMs?: number
}

export function ImportForm({ onImported, pollIntervalMs = 1000 }: Props) {
  const [arxivId, setArxivId] = useState('')
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const active = job !== null && !TERMINAL_STATES.has(job.state)

  useEffect(() => {
    if (job === null || TERMINAL_STATES.has(job.state)) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      api
        .job(job.id, controller.signal)
        .then((next) => {
          setJob(next)
          if (next.state === 'ready') onImported()
        })
        .catch((err: unknown) => {
          if (!controller.signal.aborted) setError(errorMessage(err))
        })
    }, pollIntervalMs)
    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [job, onImported, pollIntervalMs])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const created = await api.importArxiv(arxivId.trim())
      setJob(created)
      if (created.state === 'ready') onImported()
    } catch (err) {
      setJob(null)
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section aria-labelledby="import-heading" className="card">
      <h2 id="import-heading">Import from arXiv</h2>
      <form onSubmit={submit} className="inline-form">
        <label htmlFor="arxiv-id">arXiv identifier</label>
        <input
          id="arxiv-id"
          value={arxivId}
          onChange={(event) => setArxivId(event.target.value)}
          placeholder="e.g. 1706.03762"
          maxLength={64}
          required
          autoComplete="off"
        />
        <button type="submit" disabled={submitting || active || arxivId.trim() === ''}>
          {submitting ? 'Submitting…' : 'Import'}
        </button>
      </form>
      {error && (
        <p role="alert" className="status-error">
          {error}
        </p>
      )}
      {job && (
        <p role="status" aria-live="polite" className={job.state === 'failed' ? 'status-error' : undefined}>
          <strong>{job.source_ref}</strong>: {STATE_LABELS[job.state] ?? job.state}
          {job.state === 'failed' && job.error ? ` — ${job.error}` : ''}
        </p>
      )}
    </section>
  )
}
