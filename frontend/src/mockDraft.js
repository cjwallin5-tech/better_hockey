// Mock draft: you draft from a slot against bots that make the other teams' picks. Plain functions (the screen is
// components/MockDraft.jsx), built on the board from draft.js, so every player is valued over the best free pickup and a
// goalie and a center share one scale.
//
// The whole draft is a pure function of the board, the league, a seed and YOUR picks: simulate() replays it from the start each
// time, and a bot's randomness for pick n depends only on the seed and n. That makes a draft replayable from just your own picks
// (so it survives a refresh) and makes undo trivial: drop your last pick and replay.
//
// A bot is a plausible manager, not a prediction of yours. It takes the best player by value plus some noise (how much is the
// `noise` setting), prefers a position it still needs a starter at, will not stack a position past its starters plus a couple of
// bench players (one for goalies), and fills every starting slot before the draft ends. It knows nothing about ADP or the
// players' reputations, so early picks follow the value order closely and later ones are a lottery, as in a real draft.
import { GROUPS } from './value.js'
import { needs, slotAt } from './draft.js'

export const NOISE = { chalk: 0, tight: 0.04, realistic: 0.1, wild: 0.2 } // spread of a bot's mistakes, as a share of the board's value range
export const NEED_BONUS = 0.03    // value credit, as a share of the range, for a position the bot still needs a starter at
export const BENCH_EXTRA = 2      // players a bot may hold at a position beyond its starters (goalies: one)
export const LOOK = 40            // a bot considers its top this many allowed players

/** A small seeded generator (mulberry32): the same seed gives the same sequence. */
export function rng(seed) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** The generator for overall pick n: it depends only on the seed and n, never on how many picks came before. */
export const pickRng = (seed, n) => rng((seed + Math.imul(n, 0x9e3779b1)) >>> 0)

const gauss = (random) => Math.sqrt(-2 * Math.log(Math.max(1e-12, random()))) * Math.cos(2 * Math.PI * random())

/**
 * The player a bot takes. available: the board minus taken players, best first. held: the groups the bot already has.
 * picksLeft: picks this team still has, this one included. spread: the board's value range (see simulate()).
 */
export function botPick({ available, held, slots, picksLeft, noise, spread, random }) {
  const have = {}
  for (const g of held) have[g] = (have[g] ?? 0) + 1
  const open = needs(held, slots)
  const openTotal = GROUPS.reduce((t, g) => t + open[g], 0)
  const forced = picksLeft <= openTotal                       // only the open starting slots are left to fill
  const cap = (g) => (slots[g] ?? 0) + (g === 'G' ? 1 : BENCH_EXTRA)
  const candidates = []
  for (const r of available) {
    if (candidates.length >= LOOK) break
    if (open[r.group] > 0 || (!forced && (have[r.group] ?? 0) < cap(r.group))) candidates.push(r)
  }
  if (candidates.length === 0) return available[0] ?? null    // the allowed pool ran dry: take the best player left
  let best = null
  let bestScore = -Infinity
  for (const r of candidates) {
    const score = r.value + (open[r.group] > 0 ? NEED_BONUS * spread : 0) + (noise > 0 ? gauss(random) * noise * spread : 0)
    if (score > bestScore) {
      best = r
      bestScore = score
    }
  }
  return best
}

/** The value range the noise is measured against: from the best player to roughly the last starter in the league. */
export function valueSpread(board, league) {
  if (board.length === 0) return 0
  const starters = GROUPS.reduce((t, g) => t + (league.slots[g] ?? 0), 0) * league.teams
  return Math.max(1e-9, board[0].value - board[Math.min(board.length, Math.max(1, starters)) - 1].value)
}

/**
 * Plays the draft from the start. config: { league: { teams, slots }, slot, snake, rounds, seed, noise }, userPicks: the player ids you
 * took, in order. Stops when it is your turn and you have no pick queued. Returns
 *   picks:    [{ n, round, slot, id, value, bestLeft }] every pick made so far (bestLeft: the best value on the board before it);
 *   applied:  your picks that counted (one that was already taken, or not on the board, is skipped);
 *   next, onClock, waiting (your turn), done, rosters (slot -> board rows), available (the board minus taken players).
 */
export function simulate({ board, config, userPicks = [] }) {
  const { league, slot, snake = true, rounds, seed, noise } = config
  const teams = league.teams
  const total = teams * rounds
  const spread = valueSpread(board, league)
  const byId = new Map(board.map((r) => [r.id, r]))
  const pool = [...board]
  const rosters = Array.from({ length: teams + 1 }, () => [])
  const picks = []
  const applied = []
  let queued = 0
  let n = 1
  let waiting = false
  while (n <= total && pool.length > 0) {
    const s = slotAt(n, teams, snake)
    let player
    if (s === slot) {
      if (queued >= userPicks.length) {
        waiting = true
        break
      }
      const wanted = byId.get(userPicks[queued++])
      const at = wanted ? pool.indexOf(wanted) : -1
      if (at < 0) continue                                   // not available any more: skip it and look at the next queued pick
      player = wanted
      applied.push(wanted.id)
    } else {
      player = botPick({ available: pool, held: rosters[s].map((r) => r.group), slots: league.slots, picksLeft: rounds - rosters[s].length,
                         noise: NOISE[noise] ?? NOISE.realistic, spread, random: pickRng(seed, n) })
    }
    picks.push({ n, round: Math.ceil(n / teams), slot: s, id: player.id, value: player.value, bestLeft: pool[0].value })
    rosters[s].push(player)
    pool.splice(pool.indexOf(player), 1)
    n += 1
  }
  const done = n > total || pool.length === 0
  return { picks, applied, next: n, onClock: done ? null : slotAt(n, teams, snake), waiting: waiting && !done, done, rosters, available: pool }
}

/**
 * How each team's draft looks: the value of its best starting lineup (the top `slots` players at each position, anything below the free
 * pickup counting as 0), who is missing, and its rank. rosters: the simulate() result's rosters.
 */
export function teamTotals(rosters, slots) {
  const rows = []
  for (let slot = 1; slot < rosters.length; slot++) {
    let starters = 0
    let missing = 0
    for (const g of GROUPS) {
      const best = rosters[slot].filter((r) => r.group === g).map((r) => r.value).sort((a, b) => b - a)
      const want = slots[g] ?? 0
      for (let i = 0; i < want; i++) {
        if (i < best.length) starters += Math.max(0, best[i])
        else missing += 1
      }
    }
    rows.push({ slot, players: rosters[slot].length, starters, missing })
  }
  const order = [...rows].sort((a, b) => b.starters - a.starters || a.slot - b.slot)
  return rows.map((r) => ({ ...r, rank: order.findIndex((o) => o.slot === r.slot) + 1 }))
}

/** Your own picks with what was left behind: the value you took, the best on the board then, and the gap (0 when you took the best). */
export function myPickReview(picks, slot) {
  return picks.filter((p) => p.slot === slot).map((p) => ({ ...p, left: Math.max(0, p.bestLeft - p.value) }))
}
