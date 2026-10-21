// Player value for category leagues (head-to-head or roto), where you win by being better than your opponents in each of
// several categories rather than by scoring points. Same idea as value.js, different currency:
//   1. Each counting category is projected over the rest of the season: the player's per-game rate times the games they
//      are expected to play. An early rate is pulled toward the player's own record (goals, assists and points) or toward the
//      average, by a weight that depends on the stat (see categoryDefs.js: rare, luck-driven stats like shutouts and
//      plus/minus get far more pull than steady volumes like shots and hits).
//   2. Goalie ratios are valued by what they are worth in total, not as a ratio: GAA as the goals against above or below
//      the average goalie over the games he plays, save % as the saves above or below average over the shots he faces.
//      Save % is pulled very hard toward average (SV_PRIOR_SHOTS), because goaltending results barely repeat from year to
//      year (see matchups.py), so a goalie's value comes mostly from how often he plays and wins.
//   3. Each category is turned into a z-score: how far a player's projection is above the pool's average, in units of how
//      much real outcomes vary across the pool (the spread of the UNSHRUNK projections). That matters: shrinking pulls every
//      projection toward the average, and dividing by the spread of the shrunk projections would blow the leftover noise back
//      up to full size (a goalie with two early shutouts would look like a star at shutouts). Measured this way a mostly-luck
//      category gives small z-scores and a steady one gives large ones, and every value grows as the season fills in. The pool
//      is the players who would be rostered (teams x starting slots), so a scrub doesn't stretch the scale. The categories you
//      count are added up, with the sign flipped for stats where lower is better.
//   4. Value = that total minus the total of the best player at the position who would not be starting, as in value.js.
// A category you don't count adds nothing. What it does not know: that in head-to-head you only need to win a category,
// not win it by a lot, so punting a category can beat a balanced roster; z-scores favor balance. Use the per-category
// breakdown to build for your categories.
import { GOALIE_CATEGORIES, SKATER_CATEGORIES } from './categoryDefs.js'
import { DEFAULT_LEAGUE, PRIOR_WEIGHT, cleanLeague, groupOf, outlook, shrink, teamOf } from './value.js'

export const SV_PRIOR_SHOTS = 8000   // shots' worth of average goaltending (backtested on past seasons; see matchups.py)
const CLAMP = [-4, 6]                // keep one freak projection from stretching a category's scale
const SCORING_STATS = ['goals', 'assists', 'points']   // the ones with a track record (goals and assists last two seasons)

const sum = (xs) => xs.reduce((t, x) => t + x, 0)
const mean = (xs) => (xs.length ? sum(xs) / xs.length : 0)
const sd = (xs, m) => (xs.length ? Math.sqrt(sum(xs.map((x) => (x - m) ** 2)) / xs.length) : 0)
const stat = (row, key) => (key === 'points' ? (row.goals ?? 0) + (row.assists ?? 0) : row[key] ?? 0)

/**
 * z-score for each value: its distance from the mean of the values at `pool` (indexes), in units of the pool's spread.
 * The spread is measured on `scaleValues` when given (the unshrunk projections, see above), otherwise on `values`.
 * 0 when there is no spread to measure against; clamped so one freak projection can't stretch a category.
 */
export function zScores(values, pool, scaleValues = values) {
  const m = mean(pool.map((i) => values[i]))
  const scaleVals = pool.map((i) => scaleValues[i])
  const s = sd(scaleVals, mean(scaleVals))
  return values.map((v) => (s > 0 ? Math.min(CLAMP[1], Math.max(CLAMP[0], (v - m) / s)) : 0))
}

/**
 * Value for every player with a game played, under the categories your league counts. A Map from player id to
 * { id, kind, group, team, gp, hasHistory, gamesLeft, playShare, expectedGames, z: { category: z }, zsum, replacement,
 *   value, groupRank, overallRank }. Same inputs as value.playerValues, with the categories read from `league`.
 */
export function categoryValues({ skaters, goalies, league = DEFAULT_LEAGUE, gamesLeft = {}, gamesPerSeason = 84, priors = {} }) {
  const cfg = cleanLeague(league)
  const out = new Map()
  for (const kind of ['skater', 'goalie']) {
    const defs = (kind === 'goalie' ? GOALIE_CATEGORIES : SKATER_CATEGORIES).filter((d) => cfg.categories[kind].includes(d.key))
    const groups = kind === 'goalie' ? ['G'] : ['C', 'L', 'R', 'D']
    const slotsTotal = sum(groups.map((g) => cfg.slots[g]))
    const entries = (kind === 'goalie' ? goalies ?? [] : skaters ?? [])
      .filter((row) => row.games_played)
      .map((row) => ({
        row, id: row.player_id, kind, group: groupOf(row, kind), team: teamOf(row), gp: row.games_played,
        record: kind === 'skater' ? priors?.[row.player_id] ?? null : null,
      }))
    if (entries.length === 0) continue
    for (const e of entries) Object.assign(e, outlook(e.team, e.gp, gamesLeft, gamesPerSeason))

    // league-wide per-game averages among players who play regularly (not call-ups with a game or two)
    const maxGp = Math.max(...entries.map((e) => e.gp))
    const regulars = entries.filter((e) => e.gp >= Math.max(1, maxGp / 3))
    const games = sum(regulars.map((e) => e.gp))
    const avg = (key) => (games ? sum(regulars.map((e) => stat(e.row, key))) / games : 0)
    const meanShots = games ? sum(regulars.map((e) => e.row.shots_against ?? 0)) / games : 0
    const shotTotal = sum(regulars.map((e) => e.row.shots_against ?? 0))
    const meanSv = shotTotal ? sum(regulars.map((e) => e.row.saves ?? 0)) / shotTotal : 0

    // each player's projected contribution to each counted category, good = positive
    // `shrunk` false gives the plain per-game projection with nothing blended in (the measure of how much outcomes vary)
    const projection = (e, d, shrunk) => {
      const { row } = e
      const blend = (total, games, prior, weight) => (shrunk ? shrink(total, games, prior, weight) : total / games)
      if (d.key === 'gaa') {
        const rate = blend(stat(row, 'goals_against'), e.gp, avg('goals_against'), d.prior)
        return (avg('goals_against') - rate) * e.expectedGames
      }
      if (d.key === 'save_pct') {
        const shots = row.shots_against ?? 0
        const sv = shots ? blend(row.saves ?? 0, shots, meanSv, SV_PRIOR_SHOTS) : meanSv
        const perGame = blend(shots, e.gp, meanShots, GOALIE_CATEGORIES.find((x) => x.key === 'saves').prior)
        return (sv - meanSv) * perGame * e.expectedGames
      }
      let rate
      if (kind === 'goalie') {
        rate = blend(stat(row, d.key), e.gp, avg(d.key), d.prior)
      } else if (SCORING_STATS.includes(d.key)) {
        const record = e.record ? (d.key === 'goals' ? e.record.goals : d.key === 'assists' ? e.record.assists : e.record.goals + e.record.assists) : null
        rate = record == null ? blend(stat(row, d.key), e.gp, avg(d.key), PRIOR_WEIGHT.noHistory) : blend(stat(row, d.key), e.gp, record, PRIOR_WEIGHT.history)
      } else {
        rate = blend(stat(row, d.key), e.gp, avg(d.key), d.prior)
      }
      return d.sign * rate * e.expectedGames
    }
    const projected = defs.map((d) => entries.map((e) => projection(e, d, true)))   // [category][player], shrunk
    const plain = defs.map((d) => entries.map((e) => projection(e, d, false)))      // the same without any blending
    // two passes: z-scores among regulars to find who would be rostered, then again among those players
    const regularIdx = entries.map((e, i) => i).filter((i) => entries[i].gp >= Math.max(1, maxGp / 3))
    const firstZ = projected.map((col, c) => zScores(col, regularIdx, plain[c]))
    const firstSum = entries.map((_, i) => sum(firstZ.map((col) => col[i])))
    const poolSize = Math.min(entries.length, Math.max(3, cfg.teams * slotsTotal))
    const pool = entries.map((_, i) => i).sort((a, b) => firstSum[b] - firstSum[a]).slice(0, poolSize)
    const zByCat = projected.map((col, c) => zScores(col, pool, plain[c]))
    entries.forEach((e, i) => {
      e.z = Object.fromEntries(defs.map((d, c) => [d.key, zByCat[c][i]]))
      e.zsum = sum(defs.map((d, c) => zByCat[c][i]))
    })

    for (const group of groups) {
      const list = entries.filter((e) => e.group === group).sort((a, b) => b.zsum - a.zsum || a.id - b.id)
      if (list.length === 0) continue
      const replacement = list[Math.min(cfg.teams * cfg.slots[group], list.length - 1)].zsum
      list.forEach((e, i) => {
        out.set(e.id, {
          id: e.id, kind, group, team: e.team, gp: e.gp, hasHistory: Boolean(e.record) || kind === 'goalie',
          gamesLeft: e.gamesLeft, playShare: e.playShare, expectedGames: e.expectedGames,
          z: e.z, zsum: e.zsum, replacement, value: e.zsum - replacement, groupRank: i + 1,
        })
      })
    }
  }
  ;[...out.values()].sort((a, b) => b.value - a.value || a.id - b.id).forEach((v, i) => { v.overallRank = i + 1 })
  return out
}
