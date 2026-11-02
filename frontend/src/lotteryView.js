/** "12%" for a chance, "<1%" for a small one, "" for none. */
export function chance(p, digits = 0) {
  if (p == null || p < 0.0005) return ''
  if (p < 0.005 && digits === 0) return '<1%'
  return `${(p * 100).toFixed(digits)}%`
}

/** Teams worth listing: those with a real chance of the lottery (at least `min`), or everyone when `all`. */
export const visibleTeams = (teams, all, min = 0.02) => (all ? teams : teams.filter((t) => t.in_lottery >= min))

/** Background strength for a heat-table cell: 0 for nothing, up to 70 (percent of the accent colour) at a 40% chance or more. */
export const shade = (p) => (p == null || p < 0.005 ? 0 : Math.round(Math.min(1, p / 0.4) * 70))

/** The pick ordinal: 1 -> "1st", 2 -> "2nd", 11 -> "11th". */
export function ordinal(n) {
  const v = n % 100
  if (v >= 11 && v <= 13) return `${n}th`
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'}`
}

export const SORTS = {
  first_overall: (t) => -t.first_overall,
  worst_record: (t) => -t.worst_record,
  top_two: (t) => -t.top_two,
  points: (t) => t.points ?? 0,
  expected_pick: (t) => t.expected_pick ?? 99,
}
