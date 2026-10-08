import { useEffect, useState } from 'react'
import { api, errorMessage, type Job, type Stats } from '../../api/client'
import { STATE_LABELS } from '../ingest/jobLabels'

export function Dashboard({ refreshKey }: { refreshKey: number }) {
  const [stats, setStats] = useState<Stats | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.stats(), api.jobs(5)])
      .then(([s, j]) => {
        setStats(s)
        setJobs(j)
      })
      .catch((err: unknown) => setError(errorMessage(err)))
  }, [refreshKey])

  if (error)
    return (
      <p role="alert" className="status-error">
        Could not load the dashboard: {error}
      </p>
    )
  if (!stats) return <p className="muted">Loading dashboard…</p>

  const tiles: [string, number][] = [
    ['Papers', stats.papers],
    ['Pages', stats.pages],
    ['Chunks', stats.chunks],
    ['Questions answered', stats.answers_by_status.answered ?? 0],
  ]
  return (
    <section aria-labelledby="dashboard-heading" className="card">
      <h2 id="dashboard-heading">Dashboard</h2>
      <dl className="tiles">
        {tiles.map(([label, value]) => (
          <div key={label} className="tile">
            <dt>{label}</dt>
            <dd>{value.toLocaleString()}</dd>
          </div>
        ))}
      </dl>
      <p className="muted small">
        Sources: {Object.entries(stats.papers_by_source).map(([k, v]) => `${k} ${v}`).join(' · ') || 'none'} · Q&A outcomes:{' '}
        {Object.entries(stats.answers_by_status).map(([k, v]) => `${k.replace('_', ' ')} ${v}`).join(' · ') || 'none yet'}
      </p>
      <h3>Latest ingestion jobs</h3>
      {jobs.length === 0 ? (
        <p className="muted">No ingestion jobs yet.</p>
      ) : (
        <ul className="paper-list" aria-label="Latest jobs">
          {jobs.map((job) => (
            <li key={job.id}>
              <span>
                {job.display_name ?? job.source_ref} —{' '}
                <span className={job.state === 'failed' ? 'status-error' : 'muted'}>{STATE_LABELS[job.state] ?? job.state}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
