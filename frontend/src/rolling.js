// Recent form from a player's game log: how the last 5, 10 or 20 games compare with the whole season, and a
// rolling line for a trend chart. Plain functions over the game rows the player pages already load, so they can be
// tested. `games` is always CHRONOLOGICAL (oldest first); the API sends newest first, so reverse it before calling.
import { SKATER_CATS, fantasyPoints } from './fantasy.js'

export const WINDOWS = [5, 10, 20]

// Season stats the game log doesn't carry, so a fantasy rate built from game rows can't include them.
export const NOT_IN_GAME_LOG = ['pp_points', 'sh_points', 'game_winning_goals']
const GAME_CATS = SKATER_CATS.filter(([key]) => !NOT_IN_GAME_LOG.includes(key))

const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const sumOf = (rows, key) => rows.reduce((t, r) => t + (num(r[key]) ?? 0), 0)
const meanOf = (rows, key) => {
  const vals = rows.map((r) => num(r[key])).filter((v) => v !== null)
  return vals.length ? vals.reduce((t, v) => t + v, 0) / vals.length : null
}

/** The last n games (all of them for n = null). */
export const lastN = (games, n) => (n == null ? games : games.slice(Math.max(0, games.length - n)))

/** The windows worth showing: those shorter than the games played (a window as long as the season is the season). */
export const windowsFor = (count) => WINDOWS.filter((n) => n < count)

/** Scoring stats with points set that the game log can't supply (power-play bonus, game-winning goals). */
export const missingScoring = (scoring) => NOT_IN_GAME_LOG.filter((key) => Number(scoring?.[key]))

/**
 * A skater's line over the last n games (the season for n = null): totals for goals, assists, points and plus/minus,
 * per-game averages for the rest, and fantasy points per game under the given scoring (from game rows only, so
 * the season row is comparable with the windows).
 */
export function skaterForm(games, n, scoring = {}) {
  const g = lastN(games, n)
  const gp = g.length
  const points = sumOf(g, 'points')
  return {
    gp, goals: sumOf(g, 'goals'), assists: sumOf(g, 'assists'), points,
    ppg: gp ? points / gp : null,
    shots: meanOf(g, 'shots'), toi: meanOf(g, 'toi_sec'), hits: meanOf(g, 'hits'), blocks: meanOf(g, 'blocked_shots'),
    plusMinus: sumOf(g, 'plus_minus'),
    fpg: gp ? g.reduce((t, row) => t + fantasyPoints(row, GAME_CATS, scoring), 0) / gp : null,
  }
}

/** A goalie's line over his last n appearances (the season for n = null); gsaa needs the league save %. */
export function goalieForm(games, n, leagueSvPct = null) {
  const g = lastN(games, n)
  const shots = sumOf(g, 'shots_against')
  const saves = sumOf(g, 'saves')
  const against = sumOf(g, 'goals_against')
  const toi = sumOf(g, 'toi_sec')
  return {
    gp: g.length, starts: g.filter((x) => x.started).length, wins: g.filter((x) => x.decision === 'W').length,
    shots, saves, against,
    svPct: shots ? saves / shots : null,
    gaa: toi ? (against * 3600) / toi : null,
    gsaa: shots && leagueSvPct != null ? shots * (1 - leagueSvPct) - against : null,
  }
}

/** Trailing mean of valueOf(game) over w games, per game; null until a full window exists (and for gaps). */
export function rollingMean(games, w, valueOf) {
  return games.map((_, i) => {
    if (i < w - 1) return null
    const vals = games.slice(i - w + 1, i + 1).map(valueOf).filter((v) => num(v) !== null)
    return vals.length ? vals.reduce((t, v) => t + v, 0) / vals.length : null
  })
}

/** Trailing ratio of sums over w games (e.g. saves / shots); null until a full window exists or when the base is 0. */
export function rollingRatio(games, w, numerator, denominator) {
  return games.map((_, i) => {
    if (i < w - 1) return null
    const part = games.slice(i - w + 1, i + 1)
    const den = part.reduce((t, x) => t + (num(denominator(x)) ?? 0), 0)
    return den ? part.reduce((t, x) => t + (num(numerator(x)) ?? 0), 0) / den : null
  })
}
