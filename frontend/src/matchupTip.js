const RANGE = { close: 'close range', mid: 'mid-range', long: 'long range' }
const LANE = { glove: 'glove side', middle: 'the middle', blocker: 'blocker side' }

export const zoneLabel = (z) => `${RANGE[z.range]}, ${LANE[z.lane]}`.replace(', the middle', ' through the middle')
const pct = (v) => `${Math.round(v * 100)}%`
const signed = (v, d = 1) => `${v > 0 ? '+' : ''}${v.toFixed(d)}`

/**
 * One goalie-matchup line for a side's shot_fit entry (see backend/matchupfit.py): the zone that moves the fit most, how much of the
 * team's shooting comes from there against the league, and what the goalie gives up per 100 shots there against his average.
 * Positive fit means more goals for the shooting team.
 */
export function tipSentence(f) {
  const z = f.zones[0]
  const overall = f.shots_per_game ? (f.goalie_goals / f.shots_per_game) * 100 : 0
  const leaky = f.fit_goals > 0
  const where = `${zoneLabel(z)}${z.league_share != null ? ` (${pct(z.share)} of their shots, ${pct(z.league_share)} league-wide)` : ''}`
  const goalie = f.goalie.name
  const body = leaky
    ? `${goalie} gives up ${signed(z.rate_per_100)} goals per 100 shots from ${where}, against ${signed(overall)} overall.`
    : `${goalie} is better than his average from ${where}: ${signed(z.rate_per_100)} goals per 100 shots there, against ${signed(overall)} overall.`
  return `${body} Worth about ${signed(f.fit_goals, 2)} goals to ${f.team}.`
}

/** The notable tips for a game, biggest first: [{ team, fit, text, uncertain }]. uncertain marks a goalie under 60% likely to start. */
export function notableTips(shotFit, minAbs = 0) {
  if (!shotFit) return []
  return Object.values(shotFit)
    .filter((f) => f.notable && Math.abs(f.fit_goals) >= minAbs && f.zones.length > 0)
    .map((f) => ({
      team: f.team, fit: f.fit_goals, text: tipSentence(f),
      uncertain: !f.goalie.confirmed && f.goalie.probability != null && f.goalie.probability < 0.6,
      probability: f.goalie.probability, confirmed: !!f.goalie.confirmed, goalie: f.goalie.name,
    }))
    .sort((a, b) => Math.abs(b.fit) - Math.abs(a.fit))
}
