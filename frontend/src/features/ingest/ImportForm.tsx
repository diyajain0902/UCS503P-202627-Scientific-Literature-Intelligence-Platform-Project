import { useState, type FormEvent } from 'react'
import { api, errorMessage, type Job } from '../../api/client'
import { JobStatus } from './JobStatus'

interface Props {
  onImported: () => void
  pollIntervalMs?: number
}

export function ImportForm({ onImported, pollIntervalMs = 1000 }: Props) {
  const [arxivId, setArxivId] = useState('')
  const [job, setJob] = useState<Job | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const created = await api.importArxiv(arxivId.trim())
      setJob(created)
      setRunning(true)
    } catch (err) {
      setJob(null)
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section aria-labelledby="import-heading" className="card">
      <h2 id="import-heading">Import by arXiv ID</h2>
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
        <button type="submit" disabled={submitting || running || arxivId.trim() === ''}>
          {submitting ? 'Submitting…' : 'Import'}
        </button>
      </form>
      {error && (
        <p role="alert" className="status-error">
          {error}
        </p>
      )}
      {job && (
        <JobStatus
          key={job.id}
          job={job}
          pollIntervalMs={pollIntervalMs}
          onFinished={(done) => {
            setRunning(false)
            if (done.state === 'ready') onImported()
          }}
        />
      )}
    </section>
  )
}
