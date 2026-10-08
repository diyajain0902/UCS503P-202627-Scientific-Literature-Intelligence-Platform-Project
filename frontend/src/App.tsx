import { useCallback, useState } from 'react'
import { CompareView } from './features/analysis/CompareView'
import { CorpusView } from './features/corpus/CorpusView'
import { Dashboard } from './features/dashboard/Dashboard'
import { HistoryView } from './features/history/HistoryView'
import { ArxivSearch } from './features/ingest/ArxivSearch'
import { ImportForm } from './features/ingest/ImportForm'
import { RecentJobs } from './features/ingest/RecentJobs'
import { UploadForm } from './features/ingest/UploadForm'
import { QAPanel } from './features/qa/QAPanel'
import { SearchPanel } from './features/search/SearchPanel'
import { SettingsView } from './features/settings/SettingsView'
import { BackendStatus } from './features/status/BackendStatus'

const VIEWS = [
  ['dashboard', 'Dashboard'],
  ['ask', 'Ask'],
  ['search', 'Search passages'],
  ['corpus', 'Corpus'],
  ['compare', 'Compare'],
  ['add', 'Add papers'],
  ['history', 'History'],
  ['settings', 'Settings'],
] as const

type View = (typeof VIEWS)[number][0]

function App() {
  const [view, setView] = useState<View>('dashboard')
  const [version, setVersion] = useState(0)
  const changed = useCallback(() => setVersion((v) => v + 1), [])

  return (
    <>
      <header className="app-header">
        <div className="container">
          <h1>Scientific Literature Intelligence Platform</h1>
          <BackendStatus />
        </div>
      </header>
      <main className="container">
        <nav className="tabs" aria-label="Sections">
          {VIEWS.map(([id, label]) => (
            <button key={id} type="button" aria-pressed={view === id} onClick={() => setView(id)}>
              {label}
            </button>
          ))}
        </nav>
        {view === 'dashboard' && <Dashboard refreshKey={version} />}
        {view === 'ask' && <QAPanel />}
        {view === 'search' && <SearchPanel />}
        {view === 'corpus' && <CorpusView refreshKey={version} />}
        {view === 'compare' && <CompareView refreshKey={version} />}
        {view === 'add' && (
          <>
            <ArxivSearch onImported={changed} />
            <div className="grid">
              <ImportForm onImported={changed} />
              <UploadForm onImported={changed} />
            </div>
            <RecentJobs refreshKey={version} onChanged={changed} />
          </>
        )}
        {view === 'history' && <HistoryView refreshKey={version} />}
        {view === 'settings' && <SettingsView />}
      </main>
    </>
  )
}

export default App
