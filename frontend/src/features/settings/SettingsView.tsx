import { useEffect, useState } from 'react'
import { api, errorMessage, type SettingsInfo } from '../../api/client'

export function SettingsView() {
  const [settings, setSettings] = useState<SettingsInfo | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .settings()
      .then(setSettings)
      .catch((err: unknown) => setError(errorMessage(err)))
  }, [])

  const rows: [string, string][] = settings
    ? [
        ['Embedding model', `${settings.embedding_model} (${settings.embedding_dimension}-dim)`],
        ['Chunking', `${settings.chunk_window_tokens}-token window, ${settings.chunk_overlap_tokens}-token overlap`],
        ['Generation model', settings.generation_model],
        ['Generation options', Object.entries(settings.generation_options).map(([k, v]) => `${k}=${String(v)}`).join(', ')],
        ['Q&A passages / relevance threshold', `${settings.qa_default_top_k} / ${settings.qa_min_score}`],
        ['Search result limit', String(settings.search_max_top_k)],
        ['Upload limits', `${settings.max_pdf_megabytes} MB, ${settings.max_pdf_pages} pages`],
      ]
    : []

  return (
    <section aria-labelledby="settings-heading" className="card">
      <h2 id="settings-heading">Settings</h2>
      <p className="muted small">Read-only. Change these with SLIP_* environment variables and restart the backend.</p>
      {error && (
        <p role="alert" className="status-error">
          {error}
        </p>
      )}
      {settings && (
        <table className="settings-table">
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label}>
                <th scope="row">{label}</th>
                <td>{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
