import { useCallback, useEffect, useRef, useState } from 'react'
import { CompareView, type CompareSeed } from '../features/analysis/CompareView'
import { CorpusView } from '../features/corpus/CorpusView'
import { HomeView } from '../features/dashboard/HomeView'
import { HistoryView } from '../features/history/HistoryView'
import { AddPapersModal } from '../features/ingest/AddPapersModal'
import { AskView } from '../features/qa/AskView'
import type { AskRequest } from '../features/qa/QAPanel'
import { SettingsView } from '../features/settings/SettingsView'
import { BackendStatus } from '../features/status/BackendStatus'
import { Wordmark } from '../ui/controls'
import type { Tone } from '../ui/tones'
import type { View } from './route'

const NAV: [View, string, Tone][] = [
  ['home', 'Home', 'lav'],
  ['ask', 'Ask', 'mint'],
  ['library', 'Library', 'peach'],
  ['compare', 'Compare', 'sky'],
  ['history', 'History', 'lav'],
]

const TITLES: Record<View, string> = {
  home: 'Home',
  ask: 'Ask',
  library: 'Library',
  compare: 'Compare',
  history: 'History',
  settings: 'Settings',
}

const AMBIENT_KEY = 'slip.ambient'

function useAmbient(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(() => window.localStorage.getItem(AMBIENT_KEY) !== 'off')
  const set = useCallback((next: boolean) => {
    window.localStorage.setItem(AMBIENT_KEY, next ? 'on' : 'off')
    setOn(next)
  }, [])
  return [on, set]
}

interface Props {
  view: View
  onNavigate: (view: View) => void
  onLanding: () => void
  initialAddOpen?: boolean
}

/** The dashboard: glass sidebar, page header with the status pill, one view at a time. */
export function AppShell({ view, onNavigate, onLanding, initialAddOpen = false }: Props) {
  const [version, setVersion] = useState(0)
  const changed = useCallback(() => setVersion((v) => v + 1), [])
  const [addOpen, setAddOpen] = useState(initialAddOpen)
  const [askRequest, setAskRequest] = useState<AskRequest | null>(null)
  const [askVisited, setAskVisited] = useState(view === 'ask')
  const [compareSeed, setCompareSeed] = useState<CompareSeed | null>(null)
  const [historyOpen, setHistoryOpen] = useState<string | null>(null)
  const [ambient, setAmbient] = useAmbient()
  const nextId = useRef(1)

  if (view === 'ask' && !askVisited) setAskVisited(true)
  useEffect(() => {
    document.title = `${TITLES[view]} · slip`
  }, [view])

  const ask = (question: string, send: boolean) => {
    setAskRequest({ id: nextId.current++, question, send })
    onNavigate('ask')
  }
  const navTo = (next: View) => {
    setHistoryOpen(null)
    setCompareSeed(null)
    onNavigate(next)
  }

  return (
    <div className="app">
      {ambient && (
        <div className="ambient" aria-hidden="true">
          <span className="blob-1" />
          <span className="blob-2" />
          <span className="blob-3" />
        </div>
      )}
      <aside className="sidebar">
        <nav className="sidebar-panel" aria-label="Main">
          <Wordmark onClick={onLanding} />
          {NAV.map(([id, label, tone]) => (
            <button
              key={id}
              type="button"
              className={`nav-item tone-${tone}`}
              aria-current={view === id ? 'page' : undefined}
              onClick={() => navTo(id)}
            >
              <span className="dot-sq" aria-hidden="true" />
              {label}
            </button>
          ))}
          <div className="sidebar-foot">
            <button
              type="button"
              className="nav-item nav-settings"
              aria-current={view === 'settings' ? 'page' : undefined}
              onClick={() => navTo('settings')}
            >
              Settings
            </button>
            <div className="workspace">
              <span className="avatar" aria-hidden="true">
                SL
              </span>
              Local workspace
            </div>
          </div>
        </nav>
      </aside>

      <main className="main">
        <header className="page-header">
          <h1 className="page-title">{TITLES[view]}</h1>
          <div className="header-actions">
            {view === 'library' && (
              <button type="button" className="btn btn-dark btn-pill" onClick={() => setAddOpen(true)}>
                + Add papers
              </button>
            )}
            <BackendStatus />
          </div>
        </header>

        {view === 'home' && (
          <HomeView
            refreshKey={version}
            onAsk={(question) => ask(question, true)}
            onOpenAnswer={(id) => {
              setHistoryOpen(id)
              onNavigate('history')
            }}
            onNavigate={navTo}
            onAddPapers={() => {
              navTo('library')
              setAddOpen(true)
            }}
          />
        )}
        {askVisited && (
          <div hidden={view !== 'ask'}>
            <AskView request={askRequest} />
          </div>
        )}
        {view === 'library' && (
          <CorpusView
            refreshKey={version}
            onChanged={changed}
            onAskPaper={(paper) => ask(`In “${paper.title}”, `, false)}
            onComparePaper={(paper) => {
              setCompareSeed({ id: nextId.current++, paperId: paper.id })
              onNavigate('compare')
            }}
          />
        )}
        {view === 'compare' && <CompareView refreshKey={version} seed={compareSeed} />}
        {view === 'history' && <HistoryView refreshKey={version} openId={historyOpen} />}
        {view === 'settings' && <SettingsView ambient={ambient} onAmbientChange={setAmbient} />}
      </main>

      {addOpen && <AddPapersModal onClose={() => setAddOpen(false)} onImported={changed} />}
    </div>
  )
}
