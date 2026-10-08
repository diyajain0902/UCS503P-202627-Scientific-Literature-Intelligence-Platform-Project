import { useEffect, useRef, useState } from 'react'
import { api, errorMessage, TERMINAL_STATES, type Job } from '../../api/client'
import { STATE_LABELS } from './jobLabels'

interface Props {
  job: Job
  onFinished?: (job: Job) => void
  pollIntervalMs?: number
}

/** Shows a job's live state from the backend, polling until it is ready or failed. */
export function JobStatus({ job: initial, onFinished, pollIntervalMs = 1000 }: Props) {
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

  const label = job.display_name ?? job.source_ref
  return (
    <p role="status" aria-live="polite" className={job.state === 'failed' ? 'status-error' : undefined}>
      <strong>{label}</strong>: {STATE_LABELS[job.state] ?? job.state}
      {job.state === 'failed' && job.error ? ` — ${job.error}` : ''}
      {error && <span className="status-error"> (status check failed: {error})</span>}
    </p>
  )
}
