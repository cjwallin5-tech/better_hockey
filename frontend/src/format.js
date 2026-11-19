export const fmt1 = (v) => (v == null ? '–' : v.toFixed(1))
export const fmt2 = (v) => (v == null ? '–' : v.toFixed(2))
export const fmtPct = (v) => (v == null ? '–' : (v * 100).toFixed(1))
export const fmtToi = (sec) =>
  sec == null ? '–' : `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, '0')}`

// Pace from fewer games than this is mostly noise, so it's dimmed.
export const STABLE_GP = 20

/** Save percentage as .924 (a missing value as a dash). */
export const fmtSv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))

/** The weekday of a 'YYYY-MM-DD' date in the viewer's language: 'Thu' by default, 'Thursday' with 'long'. */
export const dayName = (iso, weekday = 'short') => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday })

/** 'Nov 3' for a 'YYYY-MM-DD' date. */
export const shortDate = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

/** A name without the first name ('Connor McDavid' becomes 'McDavid'). */
export const lastName = (full) => full.split(' ').slice(1).join(' ') || full
