import { useState, type ReactNode } from 'react'
import { api, errorMessage, type Analysis } from '../../api/client'
import { AnalysisResult } from './AnalysisResult'

interface Props {
  paperId: string
  /** Extra actions shown in the same row, before and after "Summarise" (the paper drawer's Ask / Compare). */
  leading?: ReactNode
  trailing?: ReactNode
}

/** Summary and structured extraction actions for one paper (FR-12, FR-14). */
export function PaperAnalysis({ paperId, leading, trailing }: Props) {
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [running, setRunning] = useState<'summary' | 'extraction' | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run(kind: 'summary' | 'extraction') {
    setRunning(kind)
    setError(null)
    try {
      setAnalysis(kind === 'summary' ? await api.summarize(paperId) : await api.extract(paperId))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setRunning(null)
    }
  }

  return (
    <div className="analysis">
      <div className="action-row">
        {leading}
        <button type="button" className="btn btn-light btn-grow" disabled={running !== null} onClick={() => void run('summary')}>
          {running === 'summary' ? 'Summarising… (local model)' : 'Summarise'}
        </button>
        {trailing}
      </div>
      <button
        type="button"
        className="btn-text"
        disabled={running !== null}
        onClick={() => void run('extraction')}
      >
        {running === 'extraction' ? 'Extracting… (local model)' : 'Extract key facts'}
      </button>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {analysis && <AnalysisResult key={analysis.id} analysis={analysis} />}
    </div>
  )
}
