import { useCallback, useEffect, useState } from 'react'
import { api, errorMessage, type Job } from '../../api/client'
import { STATE_LABELS } from './jobLabels'

export function RecentJobs({ refreshKey, onChanged }: { refreshKey: number; onChanged: () => void }) {
  const [jobs, setJobs] = useState<Job[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api
      .jobs(20)
      .then(setJobs)
      .catch((err: unknown) => setError(errorMessage(err)))
  }, [])

  useEffect(load, [load, refreshKey])

  async function retry(job: Job) {
    setError(null)
    try {
      await api.retryJob(job.id)
      load()
      onChanged()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <section aria-labelledby="jobs-heading" className="card">
      <h2 id="jobs-heading">Recent ingestion jobs</h2>
      <button type="button" className="secondary" onClick={load}>
        Refresh
      </button>
      {error && (
        <p role="alert" className="status-error">
          {error}
        </p>
      )}
      {jobs && jobs.length === 0 && <p className="muted">No jobs yet.</p>}
      {jobs && jobs.length > 0 && (
        <ul className="paper-list" aria-label="Ingestion jobs">
          {jobs.map((job) => (
            <li key={job.id}>
              <span>
                <strong>{job.display_name ?? job.source_ref}</strong>{' '}
                <span className={job.state === 'failed' ? 'status-error' : 'muted'}>
                  {STATE_LABELS[job.state] ?? job.state}
                </span>
              </span>
              <span className="muted small">
                {job.kind === 'pdf_upload' ? 'Upload' : 'arXiv'} · {new Date(job.created_at).toLocaleString()} ·
                attempts {job.attempts}
              </span>
              {job.state === 'failed' && (
                <span>
                  <span className="status-error small">{job.error}</span>{' '}
                  <button type="button" onClick={() => void retry(job)}>
                    Retry
                  </button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
