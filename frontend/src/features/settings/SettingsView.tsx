import { useEffect, useState } from 'react'
import { api, errorMessage, type SettingsInfo } from '../../api/client'

interface Props {
  ambient: boolean
  onAmbientChange: (on: boolean) => void
}

/** Read-only backend configuration (FR-23), plus the one browser-side appearance preference. */
export function SettingsView({ ambient, onAmbientChange }: Props) {
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
        ['Answer model', settings.generation_model],
        ['Embeddings', `${settings.embedding_model} · ${settings.embedding_dimension}-dim`],
        ['Chunk size', `${settings.chunk_window_tokens} tokens · ${settings.chunk_overlap_tokens} overlap`],
        ['Passages per answer', `${settings.qa_default_top_k} · min. relevance ${settings.qa_min_score}`],
        ['Generation options', Object.entries(settings.generation_options).map(([k, v]) => `${k}=${String(v)}`).join(', ')],
        ['Search result limit', String(settings.search_max_top_k)],
        ['Upload limit', `${settings.max_pdf_megabytes} MB · ${settings.max_pdf_pages} pages`],
      ]
    : []

  return (
    <div className="view narrow">
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {settings && (
        <div className="stack">
          <ul className="kv-list glass" aria-label="Backend settings">
            {rows.map(([label, value]) => (
              <li key={label}>
                <span className="kv-key">{label}</span>
                <span className="kv-value">{value}</span>
              </li>
            ))}
          </ul>
          <p className="faint small">Read-only — set via SLIP_* environment variables and restart the backend.</p>
        </div>
      )}
      <div className="stack">
        <h2 className="group-label">Appearance (this browser)</h2>
        <ul className="kv-list glass">
          <li>
            <label htmlFor="ambient" className="kv-key">
              Ambient background
            </label>
            <input
              id="ambient"
              type="checkbox"
              role="switch"
              checked={ambient}
              onChange={(event) => onAmbientChange(event.target.checked)}
            />
          </li>
        </ul>
      </div>
    </div>
  )
}
