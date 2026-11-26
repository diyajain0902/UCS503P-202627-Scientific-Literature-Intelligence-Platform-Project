import { useEffect, useRef, useState } from 'react'
import { api, errorMessage, type ReadinessResponse } from '../../api/client'
import { useEscape, useOutsideClick } from '../../ui/hooks'

const LABELS: Record<string, string> = {
  database: 'Database',
  embedding_model: 'Embeddings',
  reranker: 'Reranker',
  ollama: 'Ollama',
}

type State =
  | { kind: 'loading' }
  | { kind: 'loaded'; readiness: ReadinessResponse }
  | { kind: 'error'; message: string }

function summary(state: State): { dot: string; label: string; announce: string } {
  if (state.kind === 'loading') return { dot: 'dot-idle', label: 'Checking…', announce: 'Checking backend…' }
  if (state.kind === 'error')
    return { dot: 'dot-bad', label: 'Offline', announce: `Backend unreachable: ${state.message}` }
  if (state.readiness.status === 'ready') return { dot: 'dot-ok', label: 'Ready', announce: 'Backend ready' }
  const failing = Object.entries(state.readiness.checks)
    .filter(([, check]) => !check.ok)
    .map(([name]) => LABELS[name] ?? name)
  return { dot: 'dot-warn', label: 'Not ready', announce: `Backend not ready: ${failing.join(', ')}` }
}

/** Header status pill with a popover of readiness checks; polls /ready every 15 s. */
export function BackendStatus() {
  const [state, setState] = useState<State>({ kind: 'loading' })
  const [open, setOpen] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)
  useEscape(open, () => setOpen(false))
  useOutsideClick(wrap, open, () => setOpen(false))

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

  const { dot, label, announce } = summary(state)
  return (
    <div className="status-wrap" ref={wrap}>
      <button
        type="button"
        className="status-pill"
        aria-expanded={open}
        title="Backend status"
        onClick={() => setOpen((o) => !o)}
      >
        <span className={`dot ${dot}`} aria-hidden="true" />
        {label}
      </button>
      <span role="status" className="sr-only">
        {announce}
      </span>
      {open && (
        <div className="status-popover glass-strong">
          {state.kind === 'loaded' && (
            <ul className="status-checks" aria-label="Backend dependencies">
              {Object.entries(state.readiness.checks).map(([name, check]) => (
                <li key={name} title={check.detail}>
                  <span className={`dot ${check.ok ? 'dot-ok' : 'dot-bad'}`} aria-hidden="true" />
                  <span>{LABELS[name] ?? name}</span>
                  <span className="sr-only">: {check.ok ? 'available' : 'unavailable'} — </span>
                  <span className="check-detail">{check.detail}</span>
                </li>
              ))}
            </ul>
          )}
          {state.kind === 'loaded' && state.readiness.status !== 'ready' && (
            <p className="popover-note">Search needs the database and embeddings. Answers also need Ollama.</p>
          )}
          {state.kind === 'error' && <p className="popover-note">Cannot reach the backend API: {state.message}</p>}
          {state.kind === 'loading' && <p className="popover-note">Checking backend…</p>}
        </div>
      )}
    </div>
  )
}
