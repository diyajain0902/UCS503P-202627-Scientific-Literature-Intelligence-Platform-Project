import { useCallback, useEffect, useRef, useState } from 'react'
import { api, errorMessage, TERMINAL_STATES, type Job } from '../../api/client'
import { jobName, jobsNeedingAttention, STAGE_PROGRESS, STATE_LABELS } from './jobLabels'

interface Props {
  refreshKey: number
  onChanged: () => void
  pollIntervalMs?: number
}

/**
 * Library jobs strip (FR-17): running imports with their stage, and failed ones with Retry. Polls while anything
 * runs and calls onChanged when a job finishes, so the paper grid and stats refresh.
 */
export function RecentJobs({ refreshKey, onChanged, pollIntervalMs = 2000 }: Props) {
  const [jobs, setJobs] = useState<Job[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const running = useRef(new Set<string>())
  const changed = useRef(onChanged)
  useEffect(() => {
    changed.current = onChanged
  })

  const load = useCallback(() => {
    api
      .jobs(20)
      .then((next) => {
        const finishedNow = next.some((job) => running.current.has(job.id) && job.state === 'ready')
        running.current = new Set(next.filter((job) => !TERMINAL_STATES.has(job.state)).map((job) => job.id))
        setJobs(next)
        setError(null)
        if (finishedNow) changed.current()
      })
      .catch((err: unknown) => setError(errorMessage(err)))
  }, [])

  useEffect(load, [load, refreshKey])

  const active = jobs?.some((job) => !TERMINAL_STATES.has(job.state)) ?? false
  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(load, pollIntervalMs)
    return () => window.clearInterval(timer)
  }, [active, load, pollIntervalMs])

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

  const visible = jobs ? jobsNeedingAttention(jobs) : []
  if (!error && visible.length === 0) return null
  return (
    <section aria-label="Ingestion jobs">
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {visible.length > 0 && (
        <ul className="jobs-strip">
          {visible.map((job) => {
            const failed = job.state === 'failed'
            return (
              <li key={job.id} className={`job-row ${failed ? 'job-failed tone-rose' : 'tone-lav'}`}>
                <span className={`dot ${failed ? '' : 'dot-pulse'}`} aria-hidden="true" />
                <span className="job-name" title={jobName(job)}>
                  {jobName(job)}
                </span>
                <span className="job-state" title={failed ? (job.error ?? undefined) : undefined}>
                  {failed ? (job.error ?? 'Failed') : (STATE_LABELS[job.state] ?? job.state)}
                </span>
                <span className="job-bar" aria-hidden="true">
                  <span style={{ width: `${STAGE_PROGRESS[job.state] ?? 0}%` }} />
                </span>
                {failed && (
                  <button type="button" className="btn btn-light" onClick={() => void retry(job)}>
                    Retry
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
