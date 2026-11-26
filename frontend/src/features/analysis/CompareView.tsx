import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, errorMessage, type Analysis, type Comparison, type Paper } from '../../api/client'
import { shortTitle } from '../../ui/format'
import { useEscape, useOutsideClick } from '../../ui/hooks'
import { toneAt } from '../../ui/tones'
import { AnalysisResult } from './AnalysisResult'
import { FIELD_LABELS } from './fieldLabels'

const MAX_PAPERS = 5

/** A paper to add to the selection when the view opens (from the paper drawer). */
export interface CompareSeed {
  id: number
  paperId: string
}

/** Multi-paper comparison (FR-15) and cross-paper synthesis (FR-13). */
export function CompareView({ refreshKey, seed }: { refreshKey: number; seed?: CompareSeed | null }) {
  const [papers, setPapers] = useState<Paper[]>([])
  const [chosen, setChosen] = useState<string[]>([])
  const [pickerOpen, setPickerOpen] = useState(false)
  const [comparison, setComparison] = useState<Comparison | null>(null)
  const [topic, setTopic] = useState('')
  const [synthesis, setSynthesis] = useState<Analysis | null>(null)
  const [busy, setBusy] = useState<'compare' | 'synthesis' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const picker = useRef<HTMLDivElement>(null)
  useEscape(pickerOpen, () => setPickerOpen(false))
  useOutsideClick(picker, pickerOpen, () => setPickerOpen(false))

  useEffect(() => {
    api
      .corpus({}, 100, 0)
      .then((page) => setPapers(page.items))
      .catch((err: unknown) => setError(errorMessage(err)))
  }, [refreshKey])

  const [seeded, setSeeded] = useState<number | null>(null)
  if (seed && seed.id !== seeded) {
    setSeeded(seed.id)
    if (!chosen.includes(seed.paperId) && chosen.length < MAX_PAPERS) setChosen([...chosen, seed.paperId])
  }

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

  const byId = new Map(papers.map((p) => [p.id, p]))
  const ready = chosen.length >= 2
  return (
    <div className="view compare">
      <div className="toolbar">
        {chosen.map((id, index) => {
          const title = byId.get(id)?.title ?? id
          return (
            <span key={id} className={`pick-pill tone-${toneAt(index)}`} title={title}>
              <span className="dot-sq" aria-hidden="true" />
              {shortTitle(title)}
              <button type="button" className="pick-x" aria-label={`Remove ${title}`} onClick={() => toggle(id)}>
                ✕
              </button>
            </span>
          )
        })}
        <div className="picker-wrap" ref={picker}>
          <button type="button" className="add-pill" aria-expanded={pickerOpen} onClick={() => setPickerOpen((o) => !o)}>
            + Add
          </button>
          {pickerOpen && (
            <div className="picker glass-strong" role="dialog" aria-label="Choose papers">
              <p className="faint small">
                Choose 2 to {MAX_PAPERS} papers ({chosen.length} selected)
              </p>
              {papers.length === 0 && <p className="empty">The library is empty.</p>}
              <ul className="checklist">
                {papers.map((paper) => (
                  <li key={paper.id}>
                    <label>
                      <input
                        type="checkbox"
                        checked={chosen.includes(paper.id)}
                        disabled={!chosen.includes(paper.id) && chosen.length >= MAX_PAPERS}
                        onChange={() => toggle(paper.id)}
                      />
                      {paper.title}
                    </label>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <button type="button" className="btn btn-dark btn-pill" disabled={!ready || busy !== null} onClick={() => void compare()}>
          {busy === 'compare' ? 'Extracting and comparing… (local model)' : 'Compare key facts'}
        </button>
      </div>
      {!ready && !comparison && <p className="faint small">Pick at least two papers with “+ Add”, then compare their key facts.</p>}
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}

      {comparison && (
        <>
          {comparison.caveats.map((caveat) => (
            <p key={caveat} role="note" className="notice">
              {caveat}
            </p>
          ))}
          <div className="compare-card glass">
            <table className="compare-table" aria-label="Paper comparison">
              <thead>
                <tr>
                  <th scope="col">
                    <span className="sr-only">Field</span>
                  </th>
                  {comparison.papers.map((p) => (
                    <th key={p.paper_id} scope="col" title={p.title}>
                      {shortTitle(p.title, 48)}
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
                      return (
                        <td key={p.paper_id}>
                          {value && value.status === 'found' ? value.value : <span className="not-stated">Not stated</span>}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="faint small">
            Extracted from each paper's top passages. Values are shown side by side, never ranked. Open a paper in the
            Library to inspect its sources.
          </p>
        </>
      )}

      <form onSubmit={synthesize} className="panel glass">
        <h2>Synthesise across the selected papers</h2>
        <label htmlFor="synthesis-topic" className="field-label">
          What do the selected papers say about…
        </label>
        <div className="action-row">
          <input
            id="synthesis-topic"
            className="text-input"
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            maxLength={500}
            placeholder="e.g. how they handle long inputs"
          />
          <button type="submit" className="btn btn-dark" disabled={!ready || topic.trim() === '' || busy !== null}>
            {busy === 'synthesis' ? 'Synthesising… (local model)' : 'Synthesise'}
          </button>
        </div>
      </form>
      {synthesis && <AnalysisResult key={synthesis.id} analysis={synthesis} />}
    </div>
  )
}
