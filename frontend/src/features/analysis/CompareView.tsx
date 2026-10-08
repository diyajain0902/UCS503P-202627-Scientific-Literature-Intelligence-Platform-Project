import { useEffect, useState, type FormEvent } from 'react'
import { api, errorMessage, type Analysis, type Comparison, type Paper } from '../../api/client'
import { AnalysisResult } from './AnalysisResult'
import { FIELD_LABELS } from './fieldLabels'

const MAX_PAPERS = 5

/** Multi-paper comparison (FR-15) and cross-paper synthesis (FR-13). */
export function CompareView({ refreshKey }: { refreshKey: number }) {
  const [papers, setPapers] = useState<Paper[]>([])
  const [chosen, setChosen] = useState<string[]>([])
  const [comparison, setComparison] = useState<Comparison | null>(null)
  const [topic, setTopic] = useState('')
  const [synthesis, setSynthesis] = useState<Analysis | null>(null)
  const [busy, setBusy] = useState<'compare' | 'synthesis' | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .corpus({}, 100, 0)
      .then((page) => setPapers(page.items))
      .catch((err: unknown) => setError(errorMessage(err)))
  }, [refreshKey])

  function toggle(id: string) {
    setChosen((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : current.length < MAX_PAPERS ? [...current, id] : current,
    )
  }

  async function compare() {
    setBusy('compare')
    setError(null)
    try {
      setComparison(await api.compare(chosen))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function synthesize(event: FormEvent) {
    event.preventDefault()
    setBusy('synthesis')
    setError(null)
    try {
      setSynthesis(await api.synthesize(topic, chosen))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const ready = chosen.length >= 2
  return (
    <section aria-labelledby="compare-heading" className="card">
      <h2 id="compare-heading">Compare papers</h2>
      <fieldset>
        <legend className="muted small">Choose 2 to {MAX_PAPERS} papers ({chosen.length} selected)</legend>
        {papers.length === 0 && <p className="muted">The corpus is empty.</p>}
        <ul className="checklist">
          {papers.map((paper) => (
            <li key={paper.id}>
              <label>
                <input
                  type="checkbox"
                  checked={chosen.includes(paper.id)}
                  disabled={!chosen.includes(paper.id) && chosen.length >= MAX_PAPERS}
                  onChange={() => toggle(paper.id)}
                />{' '}
                {paper.title}
              </label>
            </li>
          ))}
        </ul>
      </fieldset>
      <button type="button" disabled={!ready || busy !== null} onClick={() => void compare()}>
        {busy === 'compare' ? 'Extracting and comparing… (local model)' : 'Compare key facts'}
      </button>
      {error && (
        <p role="alert" className="status-error">
          {error}
        </p>
      )}

      {comparison && (
        <div className="table-scroll">
          {comparison.caveats.map((caveat) => (
            <p key={caveat} role="note" className="notice">
              {caveat}
            </p>
          ))}
          <table className="compare-table" aria-label="Paper comparison">
            <thead>
              <tr>
                <th scope="col">Field</th>
                {comparison.papers.map((p) => (
                  <th key={p.paper_id} scope="col">
                    {p.title}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {comparison.fields.map((field) => (
                <tr key={field}>
                  <th scope="row">{FIELD_LABELS[field] ?? field}</th>
                  {comparison.papers.map((p) => {
                    const value = p.fields[field]
                    const known = value && value.status === 'found'
                    return (
                      <td key={p.paper_id} className={known ? undefined : 'muted'}>
                        {known ? value.value : 'Unknown'}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">Values are shown side by side, never ranked. Open a paper in Corpus to inspect sources.</p>
        </div>
      )}

      <form onSubmit={synthesize} className="stack-form synthesis-form">
        <label htmlFor="synthesis-topic">What do the selected papers say about…</label>
        <input
          id="synthesis-topic"
          value={topic}
          onChange={(event) => setTopic(event.target.value)}
          maxLength={500}
          placeholder="e.g. how they handle long inputs"
        />
        <button type="submit" disabled={!ready || topic.trim() === '' || busy !== null}>
          {busy === 'synthesis' ? 'Synthesising… (local model)' : 'Synthesise'}
        </button>
      </form>
      {synthesis && <AnalysisResult key={synthesis.id} analysis={synthesis} />}
    </section>
  )
}
