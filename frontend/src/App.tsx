import { useCallback, useState } from 'react'
import { PaperList } from './features/corpus/PaperList'
import { ImportForm } from './features/ingest/ImportForm'
import { QAPanel } from './features/qa/QAPanel'
import { SearchPanel } from './features/search/SearchPanel'
import { BackendStatus } from './features/status/BackendStatus'

type View = 'ask' | 'search'

function App() {
  const [corpusVersion, setCorpusVersion] = useState(0)
  const [view, setView] = useState<View>('ask')
  const refreshCorpus = useCallback(() => setCorpusVersion((v) => v + 1), [])

  return (
    <>
      <header className="app-header">
        <div className="container">
          <h1>Scientific Literature Intelligence Platform</h1>
          <BackendStatus />
        </div>
      </header>
      <main className="container">
        <nav className="tabs" aria-label="Mode">
          <button type="button" aria-pressed={view === 'ask'} onClick={() => setView('ask')}>
            Ask
          </button>
          <button type="button" aria-pressed={view === 'search'} onClick={() => setView('search')}>
            Search passages
          </button>
        </nav>
        {view === 'ask' ? <QAPanel /> : <SearchPanel />}
        <div className="grid">
          <ImportForm onImported={refreshCorpus} />
          <PaperList refreshKey={corpusVersion} />
        </div>
      </main>
    </>
  )
}

export default App
