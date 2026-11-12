// Small helpers for the news lists.

const MINUTE = 60
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

/** "just now", "12 min ago", "3 hr ago", "2 days ago", then a plain date for anything over a week. */
export function timeAgo(iso, now = Date.now()) {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const sec = Math.max(0, Math.round((now - then) / 1000))
  if (sec < MINUTE) return 'just now'
  if (sec < HOUR) return `${Math.floor(sec / MINUTE)} min ago`
  if (sec < DAY) return `${Math.floor(sec / HOUR)} hr ago`
  const days = Math.floor(sec / DAY)
  if (days < 7) return `${days} ${days === 1 ? 'day' : 'days'} ago`
  return new Date(then).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

/** The API query for a list of stories: only the filters that are set. */
export function newsUrl({ team, player, top, limit } = {}) {
  const q = new URLSearchParams()
  if (team) q.set('team', team)
  if (player) q.set('player', player)
  if (top) q.set('top', 'true')
  if (limit) q.set('limit', limit)
  const s = q.toString()
  return `/api/news${s ? `?${s}` : ''}`
}

/** A traded player's team is a comma list with the latest last; this is the one they play for now. */
export const currentTeam = (team) => (team || '').split(',').pop().trim()
