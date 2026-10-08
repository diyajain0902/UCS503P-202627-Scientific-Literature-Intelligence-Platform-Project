import { useEffect, useState } from 'react'
import { api, errorMessage, type ReadinessResponse } from '../../api/client'

const LABELS: Record<string, string> = {
  database: 'Database',
  embedding_model: 'Embedding model',
  ollama: 'Ollama',
}

type State =
  | { kind: 'loading' }
  | { kind: 'loaded'; readiness: ReadinessResponse }
  | { kind: 'error'; message: string }

export function BackendStatus() {
  const [state, setState] = useState<State>({ kind: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    const load = () =>
      api
        .ready(controller.signal)
        .then((readiness) => setState({ kind: 'loaded', readiness }))
        .catch((error: unknown) => {
          if (!controller.signal.aborted) setState({ kind: 'error', message: errorMessage(error) })
        })
    void load()
    const timer = window.setInterval(load, 15000)
    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [])

  if (state.kind === 'loading') return <p role="status" className="muted">Checking backend…</p>
  if (state.kind === 'error')
    return (
      <p role="status" className="status-error">
        Backend unreachable: {state.message}
      </p>
    )

  return (
    <ul className="status-list" aria-label="Backend dependencies">
      {Object.entries(state.readiness.checks).map(([name, check]) => (
        <li key={name} title={check.detail}>
          <span className={check.ok ? 'dot dot-ok' : 'dot dot-bad'} aria-hidden="true" />
          {LABELS[name] ?? name}: <span className="sr-only">{check.ok ? 'available' : 'unavailable'} — </span>
          <span className="muted">{check.detail}</span>
        </li>
      ))}
    </ul>
  )
}
