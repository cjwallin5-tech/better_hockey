// Team stats the Standings page can watch: show as a highlighted column, with a league rank, and order each group by.
// `source` says where the figure lives: the standings row itself ('team'), /api/special-teams ('special') or
// /api/score-effects ('score'); the last two are fetched only once someone picks one of their stats.
const pct1 = (v) => (v == null ? '–' : `${(v * 100).toFixed(1)}%`)
const dec = (d) => (v) => (v == null ? '–' : v.toFixed(d))
const rate3 = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))

export const TEAM_STATS = [
  { id: 'point_pct', short: 'P%', label: 'Points %', source: 'team', get: (t) => t.point_pct, fmt: rate3, tip: 'Share of the available points the team has earned' },
  { id: 'goals_for_pg', short: 'GF/GP', label: 'Goals for / game', source: 'team', get: (t) => t.goals_for_pg, fmt: dec(2), tip: 'Goals scored per game' },
  { id: 'goals_against_pg', short: 'GA/GP', label: 'Goals against / game', source: 'team', get: (t) => t.goals_against_pg, fmt: dec(2), low: true, tip: 'Goals allowed per game (fewer is better)' },
  { id: 'goal_diff_pg', short: 'Diff/GP', label: 'Goal diff / game', source: 'team', get: (t) => (t.games_played ? t.goal_diff / t.games_played : null), fmt: (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`), tip: 'Goals for minus goals against, per game' },
  { id: 'shots_for_pg', short: 'SF/GP', label: 'Shots for / game', source: 'team', get: (t) => t.shots_for_pg, fmt: dec(1), tip: 'Shots on goal per game' },
  { id: 'shots_against_pg', short: 'SA/GP', label: 'Shots against / game', source: 'team', get: (t) => t.shots_against_pg, fmt: dec(1), low: true, tip: 'Shots on goal allowed per game (fewer is better)' },
  { id: 'pp_pct', short: 'PP%', label: 'Power play %', source: 'team', get: (t) => t.pp_pct, fmt: pct1, tip: 'Power-play goals per opportunity' },
  { id: 'pk_pct', short: 'PK%', label: 'Penalty kill %', source: 'team', get: (t) => t.pk_pct, fmt: pct1, tip: 'Penalties killed per time short-handed' },
  { id: 'fo_win_pct', short: 'FO%', label: 'Faceoff %', source: 'team', get: (t) => t.fo_win_pct, fmt: pct1, tip: 'Share of faceoffs won' },
  { id: 'pp_xgf60', short: 'PP xG/60', label: 'PP xG / 60', source: 'special', get: (_t, x) => x?.pp_xgf60, fmt: dec(1), tip: 'Expected goals per 60 minutes on the power play: the quality of the chances made' },
  { id: 'pk_xga60', short: 'PK xGA/60', label: 'PK xGA / 60', source: 'special', get: (_t, x) => x?.pk_xga60, fmt: dec(1), low: true, tip: 'Expected goals against per 60 minutes short-handed (lower is better)' },
  { id: 'xg_pct', short: 'xGF%', label: 'xGF% (all situations)', source: 'score', get: (_t, x) => x?.xg_pct, fmt: pct1, tip: 'Share of expected goals while the game is on, as played' },
  { id: 'xg_pct_adj', short: 'Adj xGF%', label: 'Score-adjusted xGF%', source: 'score', get: (_t, x) => x?.xg_pct_adj, fmt: pct1, tip: 'Expected-goal share with the effect of the score removed' },
  { id: 'att_pct_adj', short: 'Adj SAT%', label: 'Score-adjusted shot share', source: 'score', get: (_t, x) => x?.att_pct_adj, fmt: pct1, tip: 'Share of shot attempts with the effect of the score removed' },
]

export const statById = (id) => TEAM_STATS.find((s) => s.id === id) ?? null

/** The stat's value for one team; `extras` maps abbrev -> that team's row from the stat's own source. */
export function statValue(stat, team, extras) {
  const v = stat.get(team, extras?.[team.abbrev])
  return v == null || Number.isNaN(v) ? null : v
}

/** Teams best-first by the stat (teams without it last); ties fall back to the order given. */
export function sortByStat(stat, teams, extras) {
  return teams
    .map((t, i) => ({ t, i, v: statValue(stat, t, extras) }))
    .sort((a, b) => {
      if (a.v == null || b.v == null) return a.v == null && b.v == null ? a.i - b.i : a.v == null ? 1 : -1
      return (stat.low ? a.v - b.v : b.v - a.v) || a.i - b.i
    })
    .map((x) => x.t)
}

/** abbrev -> league rank (1 = best, ties share a rank) for teams that have the stat. */
export function leagueRanks(stat, teams, extras) {
  const ranks = new Map()
  const valued = teams.map((t) => [t, statValue(stat, t, extras)]).filter(([, v]) => v != null)
  for (const [t, v] of valued) {
    ranks.set(t.abbrev, 1 + valued.filter(([, o]) => (stat.low ? o < v : o > v)).length)
  }
  return ranks
}
