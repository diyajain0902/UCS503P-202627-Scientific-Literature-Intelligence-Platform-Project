import { useCallback, useEffect, useState } from 'react'
import { AppShell } from './app/AppShell'
import { parseRoute, routePath, type Route } from './app/route'
import { Landing } from './features/landing/Landing'

/** Two pages without a router dependency: the landing page at "/" and the dashboard under "/app". */
function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname))
  const [addOnOpen, setAddOnOpen] = useState(false)

  useEffect(() => {
    const onPop = () => setRoute(parseRoute(window.location.pathname))
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const navigate = useCallback((next: Route) => {
    const path = routePath(next)
    if (path !== window.location.pathname) window.history.pushState(null, '', path)
    if (next.page === 'landing') document.title = 'slip · Ask your papers'
    document.documentElement.scrollTop = 0
    setRoute(next)
  }, [])

  if (route.page === 'landing')
    return (
      <Landing
        onOpenApp={(addPapers) => {
          setAddOnOpen(addPapers)
          navigate({ page: 'app', view: addPapers ? 'library' : 'home' })
        }}
      />
    )

  return (
    <AppShell
      view={route.view}
      initialAddOpen={addOnOpen}
      onNavigate={(view) => navigate({ page: 'app', view })}
      onLanding={() => navigate({ page: 'landing' })}
    />
  )
}

export default App
