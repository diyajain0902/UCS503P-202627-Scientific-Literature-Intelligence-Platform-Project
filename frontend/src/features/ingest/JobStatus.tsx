import { useEffect, useRef, useState } from 'react'
import { api, errorMessage, TERMINAL_STATES, type Job } from '../../api/client'
import { jobName, STATE_LABELS } from './jobLabels'

interface Props {
  job: Job
  onFinished?: (job: Job) => void
  pollIntervalMs?: number
  /** Hide the job name when the surrounding row already shows it. */
  showName?: boolean
}

/** Shows a job's live state from the backend, polling until it is ready or failed. */
export function JobStatus({ job: initial, onFinished, pollIntervalMs = 1000, showName = true }: Props) {
  const [job, setJob] = useState(initial)
  const [error, setError] = useState<string | null>(null)
  const finished = useRef(TERMINAL_STATES.has(initial.state))

  useEffect(() => {
    if (finished.current) {
      onFinished?.(initial)
      return
    }
    let timer: number | undefined
    const controller = new AbortController()
    const poll = () => {
      timer = window.setTimeout(() => {
        api
          .job(initial.id, controller.signal)
          .then((next) => {
            setJob(next)
            if (TERMINAL_STATES.has(next.state)) {
              finished.current = true
              onFinished?.(next)
            } else {
              poll()
            }
          })
          .catch((err: unknown) => {
            if (!controller.signal.aborted) setError(errorMessage(err))
          })
      }, pollIntervalMs)
    }
    poll()
    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
    // Poll once per job; callbacks may change identity between renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial.id, pollIntervalMs])

  const failed = job.state === 'failed'
  const running = !TERMINAL_STATES.has(job.state)
  return (
    <p role="status" aria-live="polite" className={failed ? 'job-inline is-failed' : 'job-inline'}>
      <span
        className={`dot ${failed ? 'dot-bad' : job.state === 'ready' ? 'dot-ok' : 'tone-lav'} ${running ? 'dot-pulse' : ''}`}
        aria-hidden="true"
      />
      <span>
        {showName && <strong>{jobName(job)}: </strong>}
        {STATE_LABELS[job.state] ?? job.state}
        {failed && job.error ? ` — ${job.error}` : ''}
        {error && <span className="text-bad"> (status check failed: {error})</span>}
      </span>
    </p>
  )
}
