import { useCallback, useState } from 'react'
import { PaperList } from './features/corpus/PaperList'
import { ImportForm } from './features/ingest/ImportForm'
import { SearchPanel } from './features/search/SearchPanel'
import { BackendStatus } from './features/status/BackendStatus'

function App() {
  const [corpusVersion, setCorpusVersion] = useState(0)
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
        <SearchPanel />
        <div className="grid">
          <ImportForm onImported={refreshCorpus} />
          <PaperList refreshKey={corpusVersion} />
        </div>
      </main>
    </>
  )
}

export default App
