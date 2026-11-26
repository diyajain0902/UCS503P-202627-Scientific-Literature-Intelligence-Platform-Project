import { useState } from 'react'
import type { Analysis, QACitation } from '../../api/client'
import { SourceCard } from '../qa/SourceCard'
import { toneForLabel } from '../../ui/tones'
import { FIELD_LABELS } from './fieldLabels'

function Citations({
  citations,
  selected,
  onToggle,
}: {
  citations: QACitation[]
  selected: string | null
  onToggle: (label: string) => void
}) {
  return (
    <>
      {citations
        .filter((c) => c.valid)
        .map((c) => (
          <button
            key={c.label}
            type="button"
            className={`cite tone-${toneForLabel(c.label)}`}
            aria-pressed={selected === c.label}
            aria-label={`Show source ${c.label}`}
            onClick={() => onToggle(c.label)}
          >
            {c.label}
          </button>
        ))}
    </>
  )
}

/** Renders a summary, synthesis, or extraction; every shown statement links to its source passage. */
export function AnalysisResult({ analysis }: { analysis: Analysis }) {
  const [selected, setSelected] = useState<string | null>(null)
  const toggle = (label: string) => setSelected((current) => (current === label ? null : label))
  const source = analysis.evidence.find((e) => e.label === selected)

  if (analysis.status !== 'completed') {
    const error = analysis.status === 'error'
    return (
      <div className={error ? 'declined-card error-card' : 'declined-card'}>
        <p role="status" className="declined-msg">
          <span className="dot" aria-hidden="true" />
          <span>
            <b>{error ? 'Error.' : 'Insufficient evidence.'}</b> {analysis.reason}
          </span>
        </p>
      </div>
    )
  }

  return (
    <div className="answer-card">
      {analysis.result.claims && (
        <ol className="claims-prose" aria-label={`${analysis.kind} claims`}>
          {analysis.result.claims.map((claim) => (
            <li key={claim.index}>
              {claim.text}
              <Citations citations={claim.citations} selected={selected} onToggle={toggle} />
            </li>
          ))}
        </ol>
      )}
      {analysis.result.fields && (
        <table className="kv-table" aria-label="Extracted fields">
          <tbody>
            {analysis.result.fields.map((field) => (
              <tr key={field.field}>
                <th scope="row">{FIELD_LABELS[field.field] ?? field.field}</th>
                <td>
                  {field.status === 'unknown' ? (
                    <span className="not-stated">Unknown (not stated in the retrieved passages)</span>
                  ) : (
                    field.value
                  )}
                  <Citations citations={field.citations} selected={selected} onToggle={toggle} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {source && <SourceCard evidence={source} variant="inline" onClose={() => setSelected(null)} />}
      <p className="meta-line">
        <span>{analysis.generation_model}</span>
        <span>{analysis.prompt_version}</span>
        <span>{Math.round(analysis.latency_ms)} ms</span>
      </p>
      <p className="faint small">Sources are checked; whether each passage fully supports a statement is not verified automatically.</p>
    </div>
  )
}
