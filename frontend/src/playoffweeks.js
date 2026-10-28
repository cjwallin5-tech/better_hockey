// Playoff-week planner: how your roster's schedule looks in the weeks that decide your fantasy playoffs.
//
// A fantasy week runs Monday to Sunday. The backend gives every team's remaining games with a matchup ratio per game (above 1 is soft
// for skaters; see matchups.py), so a skater's games are his team's games, and a roster's weeks are scored by the lineup optimizer (lineup.js)
// run over the chosen weeks: the expected score of the best daily lineup in each. Ratios use today's team ratings, so games far ahead are
// only as good as the ratings are today, and nothing here sees injuries or trades that have not happened yet.
import { buildEntries, optimize } from './lineup.js'

const DAY = 86400000
const parse = (iso) => new Date(`${iso}T00:00:00Z`)
const iso = (d) => d.toISOString().slice(0, 10)

/** The Monday on or before an ISO date. */
export function mondayOf(date) {
  const d = parse(date)
  return iso(new Date(d.getTime() - ((d.getUTCDay() + 6) % 7) * DAY))
}

/** Monday-to-Sunday weeks from the week of the earliest date to the week of the latest: [{ start, end }]. */
export function buildWeeks(dates) {
  if (dates.length === 0) return []
  const sorted = [...dates].sort()
  const first = parse(mondayOf(sorted[0])).getTime()
  const last = parse(mondayOf(sorted[sorted.length - 1])).getTime()
  const weeks = []
  for (let t = first; t <= last; t += 7 * DAY) weeks.push({ start: iso(new Date(t)), end: iso(new Date(t + 6 * DAY)) })
  return weeks
}

/** The index of the week holding a date, or -1. */
export const weekIndex = (date, weeks) => weeks.findIndex((w) => date >= w.start && date <= w.end)

/** The last `n` weeks as { from, to } indexes (inclusive); fantasy playoffs usually close the season out. */
export function defaultRange(weeks, n = 3) {
  return { from: Math.max(0, weeks.length - n), to: Math.max(0, weeks.length - 1) }
}

/** A saved { from, to } as week start dates, turned back into indexes; the default when it no longer fits the weeks. */
export function rangeFromSaved(saved, weeks) {
  const from = weeks.findIndex((w) => w.start === saved?.from)
  const to = weeks.findIndex((w) => w.start === saved?.to)
  return from >= 0 && to >= from ? { from, to } : defaultRange(weeks)
}

/** Back-to-backs in a list of dates: games the day after another. */
export function backToBacks(dates) {
  const sorted = [...dates].sort()
  return sorted.filter((d, i) => i > 0 && (parse(d) - parse(sorted[i - 1])) / DAY === 1).length
}

const mean = (xs) => (xs.length ? xs.reduce((t, x) => t + x, 0) / xs.length : null)

/**
 * Every team's schedule over the chosen weeks. teams: the /api/fantasy/schedule teams ({ team, name, games: [{ date, skater_ratio,
 * goalie_ratio }] }). Returns rows { team, name, weeks: [games per week], games, backToBacks, skaters, goalies, index } with the average
 * ratio for skaters and goalies and the opportunity index for skaters (the sum of ratio - 1 over the games: more games and softer
 * games both raise it).
 */
export function teamWindows(teams, weeks, range) {
  const span = weeks.slice(range.from, range.to + 1)
  const first = span[0]?.start
  const last = span[span.length - 1]?.end
  return teams.map((t) => {
    const games = t.games.filter((g) => g.date >= first && g.date <= last)
    const perWeek = span.map((w) => games.filter((g) => g.date >= w.start && g.date <= w.end).length)
    const sk = games.map((g) => g.skater_ratio).filter((r) => r != null)
    return {
      team: t.team, name: t.name, logo_url: t.logo_url, logo_dark_url: t.logo_dark_url, weeks: perWeek, games: games.length,
      backToBacks: backToBacks(games.map((g) => g.date)), skaters: mean(sk), goalies: mean(games.map((g) => g.goalie_ratio).filter((r) => r != null)),
      index: sk.reduce((s, r) => s + (r - 1), 0),
    }
  })
}

/**
 * The roster's schedule in the shape lineup.js's buildEntries reads (fantasy_week's players), from team schedules limited to a date range.
 * roster: [{ id, kind }]; teamOf(id) -> the player's team abbreviation (or undefined); gamesOut(id) -> team games missed lately.
 */
export function rosterWeek({ roster, teams, teamOf, first, last, gamesOut = () => 0 }) {
  const byTeam = new Map(teams.map((t) => [t.team, t.games]))
  const players = {}
  for (const p of roster) {
    const games = (byTeam.get(teamOf(p.id)) ?? []).filter((g) => g.date >= first && g.date <= last)
    players[p.id] = { games: games.map((g) => ({ game_date: g.date, skater_ratio: g.skater_ratio, opponent: g.opponent, home_game: g.home_game, rest: g.rest })), games_out: gamesOut(p.id) }
  }
  return players
}

/** Goalie plans limited to a date range, as buildEntries reads them. */
export const goaliesInRange = (goalies, first, last) =>
  (goalies ?? []).map((g) => ({ ...g, games: g.games.filter((x) => x.date >= first && x.date <= last) }))

/**
 * The best daily lineup across the chosen weeks and what each week of it is worth.
 * Returns { weeks: [{ start, end, games, starts, score }], total, entries, plan } where games is the games the roster's players have that
 * week, starts the ones the lineup uses, and score the expected points (or z-score in a category league) from them.
 */
export function planWeeks({ entries, slots, weeks, range }) {
  const span = weeks.slice(range.from, range.to + 1)
  const plan = optimize({ entries, slots, mode: 'daily' })
  const rows = span.map((w) => ({ ...w, games: 0, starts: 0, score: 0 }))
  for (const e of entries) {
    for (const g of e.games) {
      const row = rows[weekIndex(g.date, span)]
      if (!row) continue
      row.games += 1
      if (plan.starts.get(g.date)?.has(e.id)) { row.starts += 1; row.score += g.score }
    }
  }
  return { weeks: rows, total: rows.reduce((t, r) => t + r.score, 0), entries, plan }
}

/** Games per week for each roster entry over the chosen weeks: { id, name, group, kind, weeks: [n], total, score, out }. */
export function playerWeeks({ entries, plan, weeks, range }) {
  const span = weeks.slice(range.from, range.to + 1)
  return entries.map((e) => {
    const perWeek = span.map((w) => e.games.filter((g) => g.date >= w.start && g.date <= w.end).length)
    const stat = plan.byPlayer.get(e.id)
    return { id: e.id, name: e.name, group: e.group, kind: e.kind, known: e.known, out: e.out ?? 0, weeks: perWeek, total: perWeek.reduce((t, n) => t + n, 0), score: stat?.score ?? 0, starts: stat?.starts ?? 0 }
  })
}

export { buildEntries }
