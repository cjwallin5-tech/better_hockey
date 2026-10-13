export const fmt1 = (v) => (v == null ? '–' : v.toFixed(1))
export const fmtPct = (v) => (v == null ? '–' : (v * 100).toFixed(1))
export const fmtToi = (sec) =>
  sec == null ? '–' : `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, '0')}`

// Pace from fewer games than this is mostly noise, so it's dimmed.
export const STABLE_GP = 20
