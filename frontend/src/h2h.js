// Head-to-head matchup projector: your week against another team in your league.
//
// The site can't see other teams' rosters, so the opponent is one you enter (search or paste names). Both teams are put through
// the lineup optimizer (lineup.js) under the same slots and the same daily/weekly rule, which gives each an expected total
// for the next 7 days, and the win chance comes from how far apart those totals are against how much a week of scoring swings.
//
// The swing is a rough model, not fitted to fantasy results:
//   - a skater's game varies like points do: variance = SKATER_VARIANCE x the game's expected score x the average points per
//     goal or assist in your scoring (SKATER_VARIANCE is projections.py's backtested 1.5 variance per point)
//   - a goalie's start is worth v with chance p; given a start, the result varies by GOALIE_SD of v (a win, a shutout or a
//     blowout loss are big swings), and whether he starts at all adds p(1-p)v^2
//   - games are independent, and the two teams' totals are independent, so variances add and the margin is normal.
// It is a points-league tool: a category league scores by who wins each category, which this does not model.
import { optimize } from './lineup.js'

export const SKATER_VARIANCE = 1.5
export const GOALIE_SD = 0.6

/** Standard normal CDF (Abramowitz and Stegun 7.1.26 for erf; accurate to about 1e-7). */
export function normalCdf(z) {
  const x = Math.abs(z) / Math.SQRT2
  const t = 1 / (1 + 0.3275911 * x)
  const poly = ((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592
  const erf = 1 - poly * t * Math.exp(-x * x)
  return z >= 0 ? 0.5 * (1 + erf) : 0.5 * (1 - erf)
}

/** Average fantasy points a goal or an assist is worth in your scoring (1 when neither counts). */
export function pointScale(scoring) {
  const w = [Number(scoring?.goals) || 0, Number(scoring?.assists) || 0].filter((x) => x !== 0)
  return w.length ? w.reduce((t, x) => t + Math.abs(x), 0) / w.length : 1
}

/** Variance of one started game's score. goalie games carry a start chance (chance) and an expected score that includes it. */
export function gameVariance(entry, game, scale) {
  if (entry.kind === 'goalie') {
    const p = game.chance ?? 0
    if (p <= 0) return 0
    const v = game.score / p // what one start is worth
    return p * (GOALIE_SD * v) ** 2 + p * (1 - p) * v * v
  }
  return SKATER_VARIANCE * scale * Math.max(0, game.score)
}

/**
 * One team's week: { total, variance, days: [{ date, total }], plan, starters } where starters lists
 * { id, name, group, score, starts } for everyone with a start, best first.
 */
export function teamWeek({ entries, slots, mode, scoring, dates }) {
  const plan = optimize({ entries, slots, mode })
  const scale = pointScale(scoring)
  const days = new Map((dates ?? plan.dates).map((d) => [d, 0]))
  let total = 0
  let variance = 0
  for (const e of entries) {
    for (const g of e.games) {
      if (!plan.starts.get(g.date)?.has(e.id)) continue
      days.set(g.date, (days.get(g.date) ?? 0) + g.score)
      total += g.score
      variance += gameVariance(e, g, scale)
    }
  }
  const starters = entries
    .map((e) => ({ id: e.id, name: e.name, group: e.group, ...plan.byPlayer.get(e.id) }))
    .filter((s) => s.starts > 0)
    .sort((a, b) => b.score - a.score || a.id - b.id)
  return { total, variance, days: [...days].map(([date, t]) => ({ date, total: t })).sort((a, b) => a.date.localeCompare(b.date)), plan, starters }
}

/** Chance the first team outscores the second over the week, from the two weeks (teamWeek). Ties count as half. */
export function winChance(mine, theirs) {
  const sd = Math.sqrt(mine.variance + theirs.variance)
  if (sd === 0) return mine.total === theirs.total ? 0.5 : mine.total > theirs.total ? 1 : 0
  return normalCdf((mine.total - theirs.total) / sd)
}

// --- Entering the opponent's roster ----------------------------------------------------------------

const normalize = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim()

/** The name part of a pasted line: drops "(EDM)" and anything after " - ", " – " or a tab, and a leading list number. */
const cleanLine = (line) => line.replace(/^\s*\d+[.)]\s+/, '').replace(/\(.*?\)/g, ' ').split(/\s[-–—]\s|\t/)[0].trim()

/**
 * Players for pasted text: one name per line, or comma-separated on a single line. data = { skaters, goalies } (season rows).
 * A name that two players share matches the one with more games. Returns { matched: [{ id, kind, name }], unmatched: [text] }.
 */
export function matchNames(text, data) {
  const lines = text.includes('\n') ? text.split('\n') : text.split(/[,;]/)
  const index = new Map()
  for (const [rows, kind] of [[data?.skaters ?? [], 'skater'], [data?.goalies ?? [], 'goalie']]) {
    for (const r of rows) {
      const key = normalize(r.name)
      const cur = index.get(key)
      if (!cur || (r.games_played ?? 0) > cur.games) index.set(key, { id: r.player_id, kind, name: r.name, games: r.games_played ?? 0 })
    }
  }
  const matched = []
  const unmatched = []
  const seen = new Set()
  for (const raw of lines) {
    const name = cleanLine(raw)
    if (!name) continue
    const hit = index.get(normalize(name))
    if (!hit) unmatched.push(name)
    else if (!seen.has(hit.id)) { seen.add(hit.id); matched.push({ id: hit.id, kind: hit.kind, name: hit.name }) }
  }
  return { matched, unmatched }
}
