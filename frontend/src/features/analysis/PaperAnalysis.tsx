import { useState } from 'react'
import { api, errorMessage, type Analysis } from '../../api/client'
import { AnalysisResult } from './AnalysisResult'

/** Summary and structured extraction actions for one paper (FR-12, FR-14). */
export function PaperAnalysis({ paperId }: { paperId: string }) {
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
      <div className="inline-form">
        <button type="button" className="secondary" disabled={running !== null} onClick={() => void run('summary')}>
          {running === 'summary' ? 'Summarising… (local model)' : 'Summarise'}
        </button>
        <button type="button" className="secondary" disabled={running !== null} onClick={() => void run('extraction')}>
          {running === 'extraction' ? 'Extracting… (local model)' : 'Extract key facts'}
        </button>
      </div>
      {error && (
        <p role="alert" className="status-error">
          {error}
        </p>
      )}
      {analysis && <AnalysisResult key={analysis.id} analysis={analysis} />}
    </div>
  )
}
