const DAY_MS = 24 * 60 * 60 * 1000

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
}

function daysAgo(iso: string, now: Date): number {
  return Math.round((startOfDay(now) - startOfDay(new Date(iso))) / DAY_MS)
}

/** "just now", "12 min ago", "3 h ago" for today; the time of day for earlier days. */
export function timeLabel(iso: string, now: Date = new Date()): string {
  const then = new Date(iso)
  if (daysAgo(iso, now) === 0) {
    const minutes = Math.floor((now.getTime() - then.getTime()) / 60000)
    if (minutes < 1) return 'just now'
    if (minutes < 60) return `${minutes} min ago`
    return `${Math.floor(minutes / 60)} h ago`
  }
  return then.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

/** Like timeLabel, but names the date for anything before today (used outside day groups). */
export function whenLabel(iso: string, now: Date = new Date()): string {
  const days = daysAgo(iso, now)
  if (days === 0) return timeLabel(iso, now)
  if (days === 1) return 'yesterday'
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

export function dayLabel(iso: string, now: Date = new Date()): string {
  const days = daysAgo(iso, now)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  return new Date(iso).toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' })
}

/** Groups items by calendar day, keeping their order (items are expected newest first). */
export function groupByDay<T extends { created_at: string }>(items: T[], now: Date = new Date()) {
  const groups: { label: string; items: T[] }[] = []
  for (const item of items) {
    const label = dayLabel(item.created_at, now)
    const last = groups[groups.length - 1]
    if (last && last.label === label) last.items.push(item)
    else groups.push({ label, items: [item] })
  }
  return groups
}
