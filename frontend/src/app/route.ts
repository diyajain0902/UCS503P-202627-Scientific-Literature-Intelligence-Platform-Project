export const VIEWS = ['home', 'ask', 'library', 'compare', 'history', 'settings'] as const
export type View = (typeof VIEWS)[number]

export type Route = { page: 'landing' } | { page: 'app'; view: View }

function isView(value: string | undefined): value is View {
  return (VIEWS as readonly string[]).includes(value ?? '')
}

/** "/" is the landing page; "/app" and "/app/<view>" are the dashboard. Unknown paths show the landing page. */
export function parseRoute(pathname: string): Route {
  const match = /^\/app(?:\/([a-z]+))?\/?$/.exec(pathname)
  if (!match) return { page: 'landing' }
  return { page: 'app', view: isView(match[1]) ? match[1] : 'home' }
}

export function routePath(route: Route): string {
  if (route.page === 'landing') return '/'
  return route.view === 'home' ? '/app' : `/app/${route.view}`
}
