import { useEffect, useState } from 'react'
import { fetchHealth, type HealthResponse } from './api/client'

type ApiState =
  | { kind: 'loading' }
  | { kind: 'ok'; health: HealthResponse }
  | { kind: 'error'; message: string }

function App() {
  const [api, setApi] = useState<ApiState>({ kind: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    fetchHealth(controller.signal)
      .then((health) => setApi({ kind: 'ok', health }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setApi({ kind: 'error', message: error instanceof Error ? error.message : String(error) })
      })
    return () => controller.abort()
  }, [])

  return (
    <main>
      <h1>Scientific Literature Intelligence Platform</h1>
      <p className="muted">Grounded search and question answering over scientific papers.</p>
      <p role="status">
        {api.kind === 'loading' && 'Checking backend…'}
        {api.kind === 'ok' && (
          <span className="status-ok">Backend online (v{api.health.version})</span>
        )}
        {api.kind === 'error' && (
          <span className="status-error">Backend unreachable: {api.message}</span>
        )}
      </p>
    </main>
  )
}

export default App
