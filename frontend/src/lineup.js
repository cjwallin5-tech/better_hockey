// Lineup optimizer: who to start on each day of the coming week, given your league's slots and scoring.
//
// Every game a roster player has gets an expected score: a skater's fantasy points per game (or category z-score per game)
// scaled by how soft the opponent is, a goalie's expected points for a start there weighted by his chance to start it (see
// streaming.js). Then each position group fills its slots with the highest scores among the players who have a game.
// Positions are independent (there is no UTIL slot), so taking the best N of each group is optimal.
//   daily:  the lineup can change every day, so each day is filled from the players who play that day.
//   weekly: the lineup locks for the week, so each group takes the N players with the best week total, and a day with
//           fewer of them playing simply leaves slots empty.
// It can't see injuries (beyond a badge for players who have missed games), who your league's other teams hold, or
// whether your league scores by points or categories beyond the numbers values.js and categories.js give it.
import { windowPoints, windowTotals } from './streaming.js'

/** A skater's score for one game: their per-game rate moved by the matchup (above 1 is soft). Works for negative rates too. */
export function skaterGameScore(base, ratio) {
  const r = ratio ?? 1
  return base + Math.abs(base) * (r - 1)
}

/** The per-game rate under your league: fantasy points a game (points) or z-score a game (categories), or 0 when unknown. */
export function baseRate(v, isCats) {
  if (!v) return 0
  if (isCats) return v.expectedGames > 0 ? v.zsum / v.expectedGames : 0
  return v.shrunk ?? 0
}

/** A goalie's score for one game: his chance to start it times what a start there is worth. */
export function goalieGameScore(game, v, scoring, isCats) {
  const p = game.probability ?? 0
  if (!isCats) return windowPoints(windowTotals([game]), scoring)
  return p * baseRate(v, true)
}

/**
 * Roster entries ready to optimize: [{ id, name, kind, group, games: [{ date, score, detail }] }].
 * week: /api/fantasy/week's players ({ id: { games: [{ game_date, skater_ratio, opponent, home_game }] } });
 * streaming: /api/streaming/goalies' goalies ({ player_id, games: [{ date, probability, line, opponent, ... }] }).
 */
export function buildEntries({ roster, week, streaming, values, scoring, isCats }) {
  const goalies = new Map((streaming ?? []).map((g) => [g.player_id, g]))
  return roster.map((p) => {
    const v = values.get(p.id)
    const group = v?.group ?? (p.kind === 'goalie' ? 'G' : 'C')
    if (p.kind === 'goalie') {
      const games = (goalies.get(p.id)?.games ?? []).map((g) => ({
        date: g.date, score: goalieGameScore(g, v, scoring, isCats), opponent: g.opponent, home: g.home_game,
        chance: g.probability, confirmed: g.confirmed, back_to_back: g.back_to_back,
      }))
      return { id: p.id, name: p.name, kind: p.kind, group, games, known: Boolean(v) }
    }
    const base = baseRate(v, isCats)
    const games = (week?.[p.id]?.games ?? []).map((g) => ({
      date: g.game_date, score: skaterGameScore(base, g.skater_ratio), opponent: g.opponent, home: g.home_game, rest: g.rest,
    }))
    return { id: p.id, name: p.name, kind: p.kind, group, games, known: Boolean(v), out: week?.[p.id]?.games_out ?? 0 }
  })
}

const byScore = (a, b) => b.score - a.score || a.id - b.id

/**
 * The best lineup. entries from buildEntries; slots { C, L, R, D, G }; mode 'daily' or 'weekly'.
 * Returns { dates, starts, total, byPlayer }: dates are every day any player has a game, starts maps date -> Set of
 * starting player ids, total is the expected score of those starts, byPlayer maps id -> { starts, score, sat, satScore }
 * (sat: games he plays that he sits).
 */
export function optimize({ entries, slots, mode = 'daily' }) {
  const dates = [...new Set(entries.flatMap((e) => e.games.map((g) => g.date)))].sort()
  const starts = new Map(dates.map((d) => [d, new Set()]))
  const byPlayer = new Map(entries.map((e) => [e.id, { starts: 0, score: 0, sat: 0, satScore: 0 }]))
  let total = 0

  const groups = [...new Set(entries.map((e) => e.group))]
  for (const group of groups) {
    const n = slots?.[group] ?? 0
    const pool = entries.filter((e) => e.group === group)
    if (mode === 'weekly') {
      const week = pool.map((e) => ({ id: e.id, score: e.games.reduce((t, g) => t + g.score, 0) }))
      const chosen = new Set(week.sort(byScore).slice(0, n).map((e) => e.id))
      for (const e of pool) for (const g of e.games) {
        const stat = byPlayer.get(e.id)
        if (chosen.has(e.id)) { starts.get(g.date).add(e.id); stat.starts += 1; stat.score += g.score; total += g.score }
        else { stat.sat += 1; stat.satScore += g.score }
      }
      continue
    }
    for (const date of dates) {
      const playing = pool.map((e) => ({ id: e.id, score: e.games.filter((g) => g.date === date).reduce((t, g) => t + g.score, 0), has: e.games.some((g) => g.date === date) })).filter((e) => e.has)
      const ranked = playing.sort(byScore)
      ranked.forEach((e, i) => {
        const stat = byPlayer.get(e.id)
        if (i < n) { starts.get(date).add(e.id); stat.starts += 1; stat.score += e.score; total += e.score }
        else { stat.sat += 1; stat.satScore += e.score }
      })
    }
  }
  return { dates, starts, total, byPlayer }
}
