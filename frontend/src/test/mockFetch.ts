import { vi } from 'vitest'

type Handler = (url: string, init?: RequestInit) => Response | Promise<Response>

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** Route fetch calls by "METHOD /path" prefix; unmatched calls fail the test loudly. */
export function mockFetch(routes: Record<string, Handler>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    const key = Object.keys(routes).find((route) => {
      const [m, path] = route.split(' ')
      return m === method && url.startsWith(`/api/v1${path}`)
    })
    if (!key) throw new Error(`Unexpected fetch: ${method} ${url}`)
    return routes[key](url, init)
  })
  vi.stubGlobal('fetch', fn)
  return fn
}
