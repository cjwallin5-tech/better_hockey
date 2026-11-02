/** "+0.6" / "-0.8": expected points against an average schedule (positive = softer than average, negative = harder). */
export const fmtPts = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(1)}`)

/** Opponents' average goal margin per game, "+0.09" meaning the opponents are better than average (a harder schedule). */
export const fmtNet = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`)

/**
 * Ranks teams on a value, 1 = hardest. Returns { abbrev: rank } skipping teams without the figure. Ties share a rank order by the
 * order given, which keeps the table stable.
 */
export function difficultyRanks(rows, value) {
  const have = rows.filter((r) => value(r) != null).sort((a, b) => value(a) - value(b))
  return Object.fromEntries(have.map((r, i) => [r.team, i + 1]))
}

/** "hardest", "easiest" or '' for a rank among n: the five at each end. */
export function extreme(rank, n, k = 5) {
  if (rank == null) return ''
  if (rank <= k) return 'hardest'
  if (rank > n - k) return 'easiest'
  return ''
}

/** The largest swing in the column, in points, for the page's reminder of how small the spread is. */
export const biggestSwing = (rows, value) => Math.max(0, ...rows.map((r) => Math.abs(value(r) ?? 0)))
