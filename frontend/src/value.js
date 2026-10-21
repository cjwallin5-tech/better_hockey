// Player value for fantasy: what a player is worth over the rest of the season, above the best player you could
// pick up for free, under YOUR league's scoring. Everything here is plain functions so it can be tested.
//
// For each player:
//   1. Fantasy points per game under your scoring.
//   2. Early in a season a rate is mostly noise, so it is pulled toward what we expect (the PRIOR_WEIGHT numbers are
//      "games' worth" of that expectation). The goals-and-assists part is pulled toward the player's own record over
//      the last two seasons, which a backtest on four past seasons found predicts the rest of a season far better
//      (error 0.14 points a game, against 0.20 for pulling toward the position average, and 0.25 for no prior at
//      all). Past seasons only keep goals and assists, so every other stat (shots, hits, blocks, plus/minus...) is
//      pulled toward the position average, as is everything for a player with no record (rookies) and for goalies.
//   3. Replacement level: the shrunk rate of the best player at that position who would NOT be starting in your
//      league (the player ranked teams x starting slots + 1), so a center is compared with centers and a goalie
//      with goalies.
//   4. Value = (shrunk rate - replacement rate) x games the player is expected to play for the rest of the season.
//      Games left come from the schedule, scaled by how often the player has played so far (a goalie who starts
//      half his team's games is expected to keep doing that; injuries and healthy scratches are not predicted).
// A player at replacement level is worth 0, below it is negative.
//
// What it does not know: injuries, line and role changes still to come, schedule strength, or anything that
// happens after the data. It is a ranking aid, not a forecast.
import { SKATER_CATEGORIES, cleanCategories } from './categoryDefs.js'
import { GOALIE_CATS, SKATER_CATS, fantasyPoints } from './fantasy.js'

// Games' worth of the prior. history: goals and assists toward the player's own record (backtested; 30-60 were all
// within a hair). noHistory: goals and assists toward the position average for a player with no record (backtested at
// 5-10). other: the fallback for a skater stat categoryDefs doesn't list; the listed ones each have their own weight there
// (rare, luck-driven stats like plus/minus and game-winning goals get far more pull than shots and hits; not backtested).
// goalie: a goalie's combined fantasy rate, not backtested since past goalie game logs aren't stored; a cautious guess.
export const PRIOR_WEIGHT = { history: 40, noHistory: 10, other: 10, goalie: 12 }
const statPrior = (key) => SKATER_CATEGORIES.find((d) => d.key === key)?.prior ?? PRIOR_WEIGHT.other
export const GROUPS = ['C', 'L', 'R', 'D', 'G']
export const DEFAULT_LEAGUE = { teams: 12, slots: { C: 2, L: 2, R: 2, D: 4, G: 2 } }

/** Position group for a season row: C, L, R, D or G. */
export const groupOf = (row, kind) => (kind === 'goalie' ? 'G' : ['C', 'L', 'R', 'D'].includes(row.position) ? row.position : 'C')

/** The team a player is with now (a traded player's team is a comma list, latest last). */
export const teamOf = (row) => (row.team ?? '').split(',').pop().trim()

/** Whole numbers within bounds, falling back to the defaults for anything unusable. */
export function cleanLeague(raw) {
  const whole = (v, lo, hi, fallback) => (Number.isFinite(Number(v)) && v !== '' && v !== null ? Math.min(hi, Math.max(lo, Math.round(Number(v)))) : fallback)
  return {
    teams: whole(raw?.teams, 2, 32, DEFAULT_LEAGUE.teams),
    slots: Object.fromEntries(GROUPS.map((g) => [g, whole(raw?.slots?.[g], 0, 10, DEFAULT_LEAGUE.slots[g])])),
    // points leagues score each stat; category leagues count how many categories you win (see categories.js)
    format: raw?.format === 'categories' ? 'categories' : 'points',
    categories: cleanCategories(raw?.categories),
  }
}

/** (fantasy points + prior x group mean rate) / (games + prior). */
export const shrink = (fp, gp, mean, prior) => (fp + prior * mean) / (gp + prior)

/**
 * Games left for a player's team and the games we expect him to play in them: the schedule's games left, scaled by how
 * often he has played so far (a goalie who starts half the team's games is expected to keep doing so; injuries and
 * healthy scratches are not predicted). A team missing from gamesLeft falls back to the season length minus his games.
 */
export function outlook(team, gp, gamesLeft, gamesPerSeason) {
  const t = gamesLeft[team]
  const left = t ? t.left : Math.max(0, gamesPerSeason - gp)
  const playShare = t && t.played > 0 ? Math.min(1, gp / t.played) : 1
  return { gamesLeft: left, playShare, expectedGames: left * playShare }
}

/**
 * Value for every player with a game played: a Map from player id to
 * { id, kind, group, team, gp, fp, rate, shrunk, hasHistory, replacement, above, gamesLeft, playShare,
 *   expectedGames, projected, value, groupRank, overallRank }.
 * gamesLeft: { TEAM: { played, left } } (from /api/fantasy/games-left); a team missing from it falls back to the
 * season length minus the player's games. priors: { playerId: { goals, assists } } per-game track records
 * (from /api/fantasy/priors); players without one are pulled toward the position average instead.
 */
export function playerValues({ skaters, goalies, scoring, league = DEFAULT_LEAGUE, gamesLeft = {}, gamesPerSeason = 84, priors = {} }) {
  const cfg = cleanLeague(league)
  const wGoals = Number(scoring.goals) || 0
  const wAssists = Number(scoring.assists) || 0
  // every other skater stat your scoring counts, each pulled toward the average by its own weight
  const otherKeys = SKATER_CATS.map(([key]) => key).filter((key) => key !== 'goals' && key !== 'assists' && Number(scoring[key]))
  const byGroup = new Map(GROUPS.map((g) => [g, []]))
  for (const [rows, kind] of [[skaters, 'skater'], [goalies, 'goalie']]) {
    const cats = kind === 'goalie' ? GOALIE_CATS : SKATER_CATS
    for (const row of rows ?? []) {
      if (!row.games_played) continue
      const group = groupOf(row, kind)
      const fp = fantasyPoints(row, cats, scoring)
      // goals and assists are split out for skaters so they can be pulled toward the player's own record
      const ga = kind === 'goalie' ? 0 : (row.goals ?? 0) * wGoals + (row.assists ?? 0) * wAssists
      const record = kind === 'goalie' ? null : priors?.[row.player_id] ?? null
      byGroup.get(group).push({
        id: row.player_id, kind, group, team: teamOf(row), gp: row.games_played, fp, ga,
        stats: kind === 'goalie' ? {} : Object.fromEntries(otherKeys.map((key) => [key, row[key] ?? 0])),
        priorGa: record ? record.goals * wGoals + record.assists * wAssists : null, hasHistory: Boolean(record),
      })
    }
  }

  const out = new Map()
  for (const [group, list] of byGroup) {
    if (list.length === 0) continue
    // the average the prior pulls toward: players who play regularly, not call-ups with a game or two
    const maxGp = Math.max(...list.map((e) => e.gp))
    const regulars = list.filter((e) => e.gp >= Math.max(1, maxGp / 3))
    const regularGames = regulars.reduce((t, e) => t + e.gp, 0)
    const mean = (key) => (regularGames ? regulars.reduce((t, e) => t + e[key], 0) / regularGames : 0)
    const meanFp = mean('fp'), meanGa = mean('ga')
    const meanStat = (key) => (regularGames ? regulars.reduce((t, e) => t + (e.stats[key] ?? 0), 0) / regularGames : 0)
    for (const e of list) {
      e.rate = e.fp / e.gp
      if (group === 'G') {
        e.shrunk = shrink(e.fp, e.gp, meanFp, PRIOR_WEIGHT.goalie)
      } else {
        const ga = e.hasHistory ? shrink(e.ga, e.gp, e.priorGa, PRIOR_WEIGHT.history) : shrink(e.ga, e.gp, meanGa, PRIOR_WEIGHT.noHistory)
        e.shrunk = ga + otherKeys.reduce((t, key) => t + (Number(scoring[key]) || 0) * shrink(e.stats[key], e.gp, meanStat(key), statPrior(key)), 0)
      }
    }
    const ranked = [...list].sort((a, b) => b.shrunk - a.shrunk || a.id - b.id)
    const starters = cfg.teams * cfg.slots[group]
    const replacement = ranked[Math.min(starters, ranked.length - 1)].shrunk
    ranked.forEach((e, i) => {
      const { gamesLeft: left, playShare, expectedGames } = outlook(e.team, e.gp, gamesLeft, gamesPerSeason)
      out.set(e.id, {
        ...e, replacement, above: e.shrunk - replacement, gamesLeft: left, playShare, expectedGames,
        projected: e.shrunk * expectedGames, value: (e.shrunk - replacement) * expectedGames, groupRank: i + 1,
      })
    })
  }
  ;[...out.values()].sort((a, b) => b.value - a.value || a.id - b.id).forEach((v, i) => { v.overallRank = i + 1 })
  return out
}

/**
 * What a trade does to you: players you give vs players you get, in value over the rest of the season.
 * Unknown ids (no games played yet) count as 0 and are listed in `missing`. A side with fewer players leaves open
 * slots that a replacement-level pickup fills, which is worth 0 by definition, so no extra adjustment is needed.
 */
export function tradeSummary(giveIds, getIds, values) {
  const side = (ids) => {
    const players = ids.map((id) => values.get(id)).filter(Boolean)
    // z: for category leagues, each category's z-scores added up over the players on this side
    const z = {}
    for (const p of players) for (const [key, v] of Object.entries(p.z ?? {})) z[key] = (z[key] ?? 0) + v
    return {
      players, missing: ids.filter((id) => !values.has(id)), z,
      value: players.reduce((t, p) => t + p.value, 0), projected: players.reduce((t, p) => t + (p.projected ?? 0), 0),
    }
  }
  const give = side(giveIds)
  const get = side(getIds)
  return { give, get, net: get.value - give.value, netProjected: get.projected - give.projected }
}
