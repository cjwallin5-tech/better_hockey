// Streaming goalies: who to pick up for the next few days. The backend gives each goalie's chance to start every game in the
// window and the expected stat line of a start there (win, loss and overtime-loss chances, saves, shots, goals against,
// shutout chance, from the two teams' ratings; see backend/streaming.py). Here those are added up over the window and turned
// into fantasy points under your scoring, or into a z-score across the categories your league counts.
import { GOALIE_CATEGORIES } from './categoryDefs.js'
import { zScores } from './categories.js'

const sum = (xs) => xs.reduce((t, x) => t + x, 0)

/** Expected starts and expected stats over a goalie's games in the window: each game's line weighted by his chance to start it. */
export function windowTotals(games) {
  const t = { starts: 0, win: 0, loss: 0, otl: 0, saves: 0, shots: 0, ga: 0, shutout: 0 }
  for (const g of games) {
    const p = g.probability ?? 0
    t.starts += p
    for (const key of ['win', 'loss', 'otl', 'saves', 'shots', 'ga', 'shutout']) t[key] += p * (g.line?.[key] ?? 0)
  }
  return t
}

/** Fantasy points over the window under a points scoring (the goalie stats of fantasy.js's GOALIE_CATS). */
export function windowPoints(totals, scoring) {
  const w = (key) => Number(scoring?.[key]) || 0
  return w('wins') * totals.win + w('losses') * totals.loss + w('ot_losses') * totals.otl
    + w('saves') * totals.saves + w('goals_against') * totals.ga + w('shutouts') * totals.shutout
}

/**
 * What each counted category is worth over the window, good = positive. Counting categories are the expected totals (fewer
 * is better for losses and goals against); a ratio is valued by how much it moves your team's total over the games he plays:
 * GAA as the goals below an average goalie's over his starts, save % as the saves above an average goalie's on the same shots.
 */
export function categoryAmounts(totals, key, league) {
  const leagueSv = league.shots_pg ? 1 - league.goals_pg / league.shots_pg : 0
  switch (key) {
    case 'wins': return totals.win
    case 'losses': return -totals.loss
    case 'saves': return totals.saves
    case 'shutouts': return totals.shutout
    case 'goals_against': return -totals.ga
    case 'gaa': return totals.starts * league.goals_pg - totals.ga
    case 'save_pct': return totals.saves - leagueSv * totals.shots
    default: return 0
  }
}

/**
 * The ranked board. `plan` is the endpoint's goalies; league is { goals_pg, shots_pg }. In a points league the score is
 * projected fantasy points; in a category league it is the total z-score across the chosen goalie categories, measured
 * against all the goalies in the plan. Returns rows { id, name, team, games, totals, score, z? } best first.
 */
export function streamingBoard({ plan, scoring, categories, league }) {
  const rows = plan.map((g) => ({ id: g.player_id, name: g.name, team: g.team, games: g.games, totals: windowTotals(g.games) }))
  if (!categories) {
    for (const r of rows) r.score = windowPoints(r.totals, scoring)
  } else {
    const keys = GOALIE_CATEGORIES.filter((d) => categories.goalie.includes(d.key)).map((d) => d.key)
    const pool = rows.map((_, i) => i)
    const zByKey = keys.map((key) => zScores(rows.map((r) => categoryAmounts(r.totals, key, league)), pool))
    rows.forEach((r, i) => {
      r.z = Object.fromEntries(keys.map((key, c) => [key, zByKey[c][i]]))
      r.score = sum(keys.map((key, c) => zByKey[c][i]))
    })
  }
  return rows.sort((a, b) => b.score - a.score || a.id - b.id)
}
