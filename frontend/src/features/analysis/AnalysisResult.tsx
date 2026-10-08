import { useState } from 'react'
import { formatPages, type Analysis, type AnalysisEvidence, type QACitation } from '../../api/client'
import { FIELD_LABELS } from './fieldLabels'

function Citations({ citations, onShow }: { citations: QACitation[]; onShow: (label: string) => void }) {
  return (
    <>
      {citations
        .filter((c) => c.valid)
        .map((c) => (
          <button key={c.label} type="button" className="chip" aria-label={`Show source ${c.label}`} onClick={() => onShow(c.label)}>
            {c.label}
          </button>
        ))}
    </>
  )
}

function Source({ evidence }: { evidence: AnalysisEvidence }) {
  return (
    <section aria-label="Citation inspector" className="inspector">
      <h3>
        Source {evidence.label}: {evidence.paper_title}
      </h3>
      <p className="muted small">
        {evidence.arxiv_id && `arXiv:${evidence.arxiv_id}v${evidence.arxiv_version} · `}
        {formatPages(evidence.page_start, evidence.page_end)}
      </p>
      <blockquote className="passage">{evidence.text}</blockquote>
    </section>
  )
}


/** Renders a summary, synthesis, or extraction; every shown statement links to its source passage. */
export function AnalysisResult({ analysis }: { analysis: Analysis }) {
  const [selected, setSelected] = useState<string | null>(null)
  const source = analysis.evidence.find((e) => e.label === selected)

  if (analysis.status !== 'completed') {
    return (
      <p role="status" className={analysis.status === 'error' ? 'status-error' : 'notice'}>
        <strong>{analysis.status === 'error' ? 'Error.' : 'Insufficient evidence.'}</strong> {analysis.reason}
      </p>
    )
  }

  return (
    <div className="answer">
      {analysis.result.claims && (
        <ol className="claims" aria-label={`${analysis.kind} claims`}>
          {analysis.result.claims.map((claim) => (
            <li key={claim.index}>
              {claim.text} <Citations citations={claim.citations} onShow={setSelected} />
            </li>
          ))}
        </ol>
      )}
      {analysis.result.fields && (
        <table className="settings-table" aria-label="Extracted fields">
          <tbody>
            {analysis.result.fields.map((field) => (
              <tr key={field.field}>
                <th scope="row">{FIELD_LABELS[field.field] ?? field.field}</th>
                <td className={field.status === 'unknown' ? 'muted' : undefined}>
                  {field.status === 'unknown' ? 'Unknown (not stated in the retrieved passages)' : field.value}{' '}
                  <Citations citations={field.citations} onShow={setSelected} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {source && <Source evidence={source} />}
      <p className="muted small">
        {analysis.generation_model} · {analysis.prompt_version} · {Math.round(analysis.latency_ms)} ms · Sources are checked;
        whether each passage fully supports a statement is not verified automatically.
      </p>
    </div>
  )
}
