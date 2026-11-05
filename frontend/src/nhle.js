/** NHLe: a prospect's scoring in his league translated to NHL points over a full season (see backend/nhle.py). n is the API's `nhle`
 *  object ({points, low, high, factor, pairs}) or null. */
export const nhleText = (n) => (n ? String(Math.round(n.points)) : '–')

/** "2025-26" for 20252026. */
const seasonText = (id) => `${String(id).slice(0, 4)}-${String(id).slice(6)}`

/** The tooltip for an NHLe figure: the range, the factor and how many players it was fitted on. */
export function nhleTitle(n, games = 84) {
  if (!n) return 'No NHLe: a goalie, a league we have no factor for, or no season of 20 or more games yet'
  const basis = n.earlier ? `Based on his ${seasonText(n.season_id)} season, since this one is under 20 games. ` : ''
  const age = n.age_mult && Math.abs(n.age_mult - 1) >= 0.005 ? ` Adjusted by ${n.age_mult.toFixed(2)} for his age.` : ''
  return `${basis}About ${Math.round(n.points)} points over ${games} NHL games at that rate (range ${Math.round(n.low)} to ${Math.round(n.high)}). `
    + `Factor ${n.factor.toFixed(2)} from ${n.pairs} players who went from this league to the NHL.${age}`
}

/** The sentence for a prospect's page, or null without an NHLe. */
export function nhleSentence(n, league, games = 84) {
  if (!n) return null
  const when = n.earlier ? `his ${seasonText(n.season_id)}` : "this season's"
  return `At ${when} ${n.earlier ? '' : `${league} `}rate he would score about ${Math.round(n.points)} points over ${games} NHL games `
    + `(range ${Math.round(n.low)} to ${Math.round(n.high)}), if he gets there.`
}

/** A factor as a share: 0.31 reads "31%". */
export const factorPct = (f) => `${Math.round(f * 100)}%`
