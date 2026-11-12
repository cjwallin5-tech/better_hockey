// Helpers for the team season calendar. Dates are plain 'YYYY-MM-DD' strings throughout (a game belongs to the date it is played on),
// so nothing here depends on the viewer's time zone.

const pad = (n) => String(n).padStart(2, '0')
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

/** The months ('2026-10') that a list of games falls in, earliest first. */
export const monthsOf = (games) => [...new Set(games.map((g) => g.date.slice(0, 7)))].sort()

/** The month a calendar opens on: the current month, or the first month before the season starts, or the last once it is over. */
export function defaultMonth(months, today) {
  const now = today.slice(0, 7)
  if (months.includes(now)) return now
  if (!months.length) return null
  return now < months[0] ? months[0] : months[months.length - 1]
}

/** "October 2026" for '2026-10'. */
export function monthTitle(month) {
  const [y, m] = month.split('-').map(Number)
  return `${MONTHS[m - 1]} ${y}`
}

/** "Oct" style short name for '2026-10'. */
export const monthShort = (month) => MONTHS[Number(month.slice(5, 7)) - 1].slice(0, 3)

/**
 * The weeks of a month, Sunday first: an array of 7-cell rows. A cell is null (outside the month) or { date, day, game }, where game is
 * the entry from `byDate` (a Map of date -> game) or undefined.
 */
export function monthWeeks(month, byDate) {
  const [y, m] = month.split('-').map(Number)
  const lead = new Date(Date.UTC(y, m - 1, 1)).getUTCDay()
  const days = new Date(Date.UTC(y, m, 0)).getUTCDate()
  const cells = Array.from({ length: lead }, () => null)
  for (let d = 1; d <= days; d++) {
    const date = `${y}-${pad(m)}-${pad(d)}`
    cells.push({ date, day: d, game: byDate.get(date) })
  }
  while (cells.length % 7) cells.push(null)
  return Array.from({ length: cells.length / 7 }, (_, i) => cells.slice(i * 7, i * 7 + 7))
}

/** { w, l, otl } for the finished games in a list. */
export function recordOf(games) {
  const r = { w: 0, l: 0, otl: 0 }
  for (const g of games) {
    if (g.result === 'W') r.w++
    else if (g.result === 'L') r.l++
    else if (g.result === 'OTL') r.otl++
  }
  return r
}

/** "12-4-1" for a record, or '' when nothing has been played. */
export const recordText = (r) => (r.w + r.l + r.otl ? `${r.w}-${r.l}-${r.otl}` : '')

/** "W 4-2", "OTL 2-3 OT", "W 3-2 SO": the result line of a finished game. */
export const resultText = (g) => `${g.result} ${g.us}-${g.them}${g.period ? ` ${g.period}` : ''}`

/** Today's date in the viewer's own time zone, as 'YYYY-MM-DD'. */
export const todayIso = (now = new Date()) => `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
