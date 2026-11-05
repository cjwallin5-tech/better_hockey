const n0 = (v) => Math.round(v)
const plural = (n, one, many) => (n === 1 ? one : many)

/** One-line story behind a goalie's projected finish: what he has now plus what is expected from the starts to come.
 *  p is a row of /api/projections/goalies. Returns null when there are no starts left to speak of. */
export function goalieProjectionNote(p) {
  const starts = n0(p.rest_starts)
  if (starts < 1) return `No more starts are expected: he finishes with the ${p.wins} ${plural(p.wins, 'win', 'wins')} he has.`
  return `${p.wins} ${plural(p.wins, 'win', 'wins')} so far, plus about ${n0(p.rest_wins)} over the ${starts} ${plural(starts, 'start', 'starts')} still to come.`
}

/** Save percentage the way hockey writes it: .912, or a dash when there is none. */
export const fmtSavePct = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))

/** Goals against average to two decimals, or a dash. */
export const fmtGaa = (v) => (v == null ? '–' : v.toFixed(2))

/** The 80% range for one projected total ('wins', 'saves', 'goals_against' or 'shutouts') as text: "34–44". Shutouts keep a decimal. */
export function goalieRange(p, stat = 'wins') {
  const low = p['low_' + stat], high = p['high_' + stat]
  if (low == null || high == null) return '–'
  return stat === 'shutouts' ? `${low.toFixed(1)}–${high.toFixed(1)}` : `${n0(low)}–${n0(high)}`
}

/** The figures shown under the headline number. */
export function goalieProjectionFigures(p) {
  return [
    { label: 'saves', value: n0(p.final_saves) },
    { label: 'save %', value: fmtSavePct(p.final_save_pct) },
    { label: 'goals against', value: n0(p.final_goals_against) },
    { label: 'GAA', value: fmtGaa(p.final_gaa) },
    { label: 'shutouts', value: p.final_shutouts.toFixed(1) },
    { label: 'starts left', value: n0(p.rest_starts) },
  ]
}
