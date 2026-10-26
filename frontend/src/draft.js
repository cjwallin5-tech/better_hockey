// Draft helper: a board of who is left, in tiers, with what your team still needs, plus keeper values. Plain functions so
// they can be tested; the screen is components/DraftHelper.jsx.
//
// Everything is built on the player values from value.js (points leagues) or categories.js (category leagues): value over
// the best player you could pick up for free, over the rest of this season, so a center and a goalie are on one scale. That
// means the board only covers players with a game played this season, and it is only as good as those values (it knows
// nothing about injuries, rookies who haven't played, or other managers' tendencies, so it is not an ADP).
//
// - Tiers: within a position, a new tier starts where the value drops by at least TIER_GAP of the position's top-to-
//   cutoff spread. Players in a tier are close enough in value that taking either is about the same; the cliff after
//   a tier is the reason to take one now.
// - Snake or straight order: who picks at each number, and when your next picks come.
// - Needs: starting slots (from your league settings) not yet filled by your picks.
// - Keepers: a player kept in round R costs the pick, so the surplus is his value minus the value of the player who
//   typically goes at that spot of the round (the value ranked at that overall pick on the value board).
import { GROUPS } from './value.js'

export const TIER_GAP = 0.08

/** The group's players best first, each with a tier number starting at 1. rows: [{ id, value, group }] for ONE group. */
export function tierGroup(rows, cutoff) {
  const sorted = [...rows].sort((a, b) => b.value - a.value || a.id - b.id)
  const span = sorted.length ? sorted[0].value - sorted[Math.min(cutoff, sorted.length) - 1 || 0].value : 0
  const gap = Math.max(span * TIER_GAP, 1e-9)
  let tier = 1
  return sorted.map((r, i) => {
    if (i > 0 && sorted[i - 1].value - r.value >= gap) tier += 1
    return { ...r, tier }
  })
}

/**
 * The whole board: every player with a value, best first, with group rank and tier. values: Map id -> { value, group, ... }
 * (value.js / categories.js); info: Map id -> { name, team, position, kind }. league: cleaned league ({ teams, slots }).
 * Players the info map doesn't know are left out.
 */
export function buildBoard({ values, info, league }) {
  const byGroup = new Map(GROUPS.map((g) => [g, []]))
  for (const [id, v] of values) {
    const who = info.get(id)
    if (who && byGroup.has(v.group)) byGroup.get(v.group).push({ id, value: v.value, group: v.group, ...who })
  }
  const all = []
  for (const [group, rows] of byGroup) {
    const cutoff = Math.max(3, league.teams * (league.slots[group] ?? 0) * 2)
    const tiered = tierGroup(rows, cutoff)
    tiered.forEach((r, i) => all.push({ ...r, groupRank: i + 1 }))
  }
  all.sort((a, b) => b.value - a.value || a.id - b.id)
  return all.map((r, i) => ({ ...r, overall: i + 1 }))
}

// --- Draft order ----------------------------------------------------------------------------------

/** Which team (slot 1..teams) makes overall pick n (1-based). snake reverses the order every other round. */
export function slotAt(n, teams, snake = true) {
  const round = Math.ceil(n / teams)
  const i = (n - 1) % teams
  return snake && round % 2 === 0 ? teams - i : i + 1
}

export const roundOf = (n, teams) => Math.ceil(n / teams)

/** The next `count` overall picks (from `from` on) that belong to `slot`. */
export function myPicks({ slot, teams, snake = true, from = 1, count = 3 }) {
  const out = []
  const last = from + teams * 2 * (count + 1) // every team picks at least once in any 2 consecutive rounds
  for (let n = from; n <= last && out.length < count; n++) if (slotAt(n, teams, snake) === slot) out.push(n)
  return out
}

// --- Needs and recommendations --------------------------------------------------------------------

/** Open starting slots by group, given the groups of your picks: { C: 1, L: 0, ... } (never below 0). */
export function needs(myGroups, slots) {
  const have = {}
  for (const g of myGroups) have[g] = (have[g] ?? 0) + 1
  return Object.fromEntries(GROUPS.map((g) => [g, Math.max(0, (slots[g] ?? 0) - (have[g] ?? 0))]))
}

/**
 * What to take now: the best player left overall, and the best one at a position you still need. When every starting slot
 * is full the best-for-need is the best overall. available is the board minus taken players, best first.
 */
export function recommend(available, open) {
  const best = available[0] ?? null
  const forNeed = available.find((r) => (open[r.group] ?? 0) > 0) ?? best
  return { best, forNeed }
}

/** Per position: how many players are left in the top tier still on the board, and the value lost moving to the next tier. */
export function tierCliffs(available) {
  const out = {}
  for (const g of GROUPS) {
    const rows = available.filter((r) => r.group === g)
    if (rows.length === 0) continue
    const top = rows[0].tier
    const inTop = rows.filter((r) => r.tier === top).length
    const next = rows.find((r) => r.tier > top)
    out[g] = { tier: top, left: inTop, best: rows[0].value, drop: next ? rows[0].value - next.value : null }
  }
  return out
}

// --- Keepers --------------------------------------------------------------------------------------

/** The value of the player who typically goes at the middle of round `round` in a league of `teams`, from the full board. */
export function roundValue(board, round, teams) {
  if (board.length === 0) return 0
  const overall = (round - 1) * teams + Math.ceil(teams / 2)
  return board[Math.min(board.length, overall) - 1].value
}

/**
 * For each kept candidate { id, round }: value, what a round-`round` pick usually gets, and the surplus. Returns rows with
 * `keep` true for the best `max` by surplus among those with a surplus above 0 (best first overall).
 */
export function keeperRows(candidates, board, teams, max) {
  const byId = new Map(board.map((r) => [r.id, r]))
  const rows = candidates
    .map((c) => ({ ...c, player: byId.get(c.id) ?? null }))
    .filter((r) => r.player && Number.isFinite(r.round) && r.round >= 1)
    .map((r) => {
      const typical = roundValue(board, r.round, teams)
      return { ...r, value: r.player.value, typical, surplus: r.player.value - typical }
    })
    .sort((a, b) => b.surplus - a.surplus || a.id - b.id)
  const keepIds = new Set(rows.filter((r) => r.surplus > 0).slice(0, Math.max(0, max)).map((r) => r.id))
  return rows.map((r) => ({ ...r, keep: keepIds.has(r.id) }))
}
