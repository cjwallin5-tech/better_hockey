// Where a goalie ranks among goalies for the stat cards on his page, the way the skater page ranks a skater among his position group.
const sv = (v) => v.toFixed(3).replace(/^0/, '')
const signed2 = (v) => `${v > 0 ? '+' : ''}${v.toFixed(2)}`

// higher: whether a bigger number is better. The percentile is the share of peers he is at least as good as.
export const GOALIE_STATS = [
  { key: 'save_pct', label: 'Save %', fmt: sv, higher: true },
  { key: 'gaa', label: 'Goals against average', fmt: (v) => v.toFixed(2), higher: false, note: 'lower is better' },
  { key: 'gsaa', label: 'Goals saved above average', fmt: signed2, higher: true },
  { key: 'gsaa_per60', label: 'Goals saved above average / 60', fmt: signed2, higher: true },
  { key: 'quality_start_pct', label: 'Quality start %', fmt: sv, higher: true },
  { key: 'shutouts', label: 'Shutouts', higher: true },
]

/** The goalies a goalie is measured against: those with at least half the starts of the busiest one (so it scales through the season). */
export function goaliePeers(goalies) {
  const most = Math.max(0, ...goalies.map((g) => g.games_started ?? 0))
  const minStarts = Math.max(1, Math.ceil(most / 2))
  return { peers: goalies.filter((g) => (g.games_started ?? 0) >= minStarts), minStarts }
}

/** 0-100 share of `values` that `value` is at least as good as, or null with no value or no peers. */
export function percentileAmong(value, values, higher) {
  const peers = values.filter((v) => v != null)
  if (value == null || peers.length === 0) return null
  const beaten = peers.filter((v) => (higher ? v <= value : v >= value)).length
  return Math.round((100 * beaten) / peers.length)
}

/** { percentiles: { stat key: 0-100 or null }, peerCount, minStarts } for one goalie against the season's goalies. */
export function goaliePercentiles(goalie, goalies) {
  const { peers, minStarts } = goaliePeers(goalies ?? [])
  const percentiles = {}
  for (const s of GOALIE_STATS) percentiles[s.key] = percentileAmong(goalie[s.key], peers.map((p) => p[s.key]), s.higher)
  return { percentiles, peerCount: peers.length, minStarts }
}
