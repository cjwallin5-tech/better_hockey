// Trade-partner finder: with the other teams' rosters known (a private league), look for trades that make both teams better.
//
// Value over replacement is not enough to judge a trade, because only the players who start count. A team with four good centers
// and two center slots gains nothing from a fifth, but would gain from a winger. So each team is scored by its lineup value: the
// best players it can start in each position group (your league's slots), summed, where a player at or below replacement level
// adds nothing (the team can always pick up a replacement). A trade's gain for a team is the change in that number.
//
// Candidate trades are one-for-one, two-for-one and one-for-two between you and one other team, using only players who add value.
// A trade is kept when it helps you and, by default, helps them too, by at least MIN_SHARE of each team's lineup value (so the gain
// means something in whatever unit the values are in, fantasy points or category z-scores). Each team gets a few of the best, with
// no player in two of its suggestions. This is the model's view of a fair trade: it can't see injuries, keepers, a manager's
// favorites or what is on their bench for a reason, and early in a season the values are noisy.
import { GROUPS } from './value.js'

export const MIN_SHARE = 0.01
export const MAX_PER_TEAM = 3

/** The players on a roster who would start, by group: the best `slots[group]` with a value above 0. Returns a Set of ids. */
export function starters(ids, values, slots) {
  const byGroup = new Map()
  for (const id of ids) {
    const v = values.get(id)
    if (!v || !(v.value > 0)) continue
    if (!byGroup.has(v.group)) byGroup.set(v.group, [])
    byGroup.get(v.group).push({ id, value: v.value })
  }
  const out = new Set()
  for (const [group, rows] of byGroup) {
    rows.sort((a, b) => b.value - a.value || a.id - b.id)
    for (const r of rows.slice(0, slots[group] ?? 0)) out.add(r.id)
  }
  return out
}

/** A roster's lineup value: the summed value of its starters. */
export function lineupValue(ids, values, slots) {
  let total = 0
  for (const id of starters(ids, values, slots)) total += values.get(id).value
  return total
}

const without = (ids, drop) => ids.filter((id) => !drop.includes(id))

// every set of one or two players
function groupsOf(ids) {
  const out = ids.map((id) => [id])
  for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) out.push([ids[i], ids[j]])
  return out
}

/**
 * Trades between you and each other team.
 *  mine: your player ids. teams: [{ id, name, players: [{ id }] }] (the others). values: Map id -> { value, group }.
 *  slots: starters per group ({ C, L, R, D, G }). requireBoth: keep only trades that help the other team too (default true).
 *  sort: 'mine' (biggest gain for you) or 'balanced' (the smaller of the two gains, biggest first).
 * Returns [{ team: { id, name }, give, get, gainMine, gainTheirs, mineBefore, theirBefore, startsMine, startsTheirs }] best first,
 * where startsMine / startsTheirs list the incoming players who would start for that side.
 */
export function findTrades({ mine, teams, values, slots, requireBoth = true, sort = 'mine', perTeam = MAX_PER_TEAM, limit = 20 }) {
  const useful = (ids) => ids.filter((id) => values.get(id)?.value > 0)
  const mineBefore = lineupValue(mine, values, slots)
  const myChips = useful(mine)
  const all = []
  for (const team of teams) {
    const theirs = team.players.map((p) => p.id).filter((id) => !mine.includes(id))
    if (theirs.length === 0) continue
    const theirBefore = lineupValue(theirs, values, slots)
    const theirChips = useful(theirs)
    const found = []
    for (const give of groupsOf(myChips)) {
      for (const get of groupsOf(theirChips)) {
        if (give.length === 2 && get.length === 2) continue            // two-for-two is left out: too many combinations to mean much
        const mineAfter = [...without(mine, give), ...get]
        const theirAfter = [...without(theirs, get), ...give]
        const gainMine = lineupValue(mineAfter, values, slots) - mineBefore
        const gainTheirs = lineupValue(theirAfter, values, slots) - theirBefore
        if (gainMine < MIN_SHARE * Math.max(mineBefore, 1e-9) || gainMine <= 0) continue
        if (requireBoth && gainTheirs < MIN_SHARE * Math.max(theirBefore, 1e-9)) continue
        found.push({ team: { id: team.id, name: team.name }, give, get, gainMine, gainTheirs, mineBefore, theirBefore })
      }
    }
    const key = sort === 'balanced' ? (t) => Math.min(t.gainMine, t.gainTheirs) : (t) => t.gainMine
    found.sort((a, b) => key(b) - key(a) || a.give.length + a.get.length - b.give.length - b.get.length || a.give[0] - b.give[0] || a.get[0] - b.get[0])
    const used = new Set()
    let kept = 0
    for (const t of found) {
      if (kept >= perTeam) break
      const ids = [...t.give, ...t.get]
      if (ids.some((id) => used.has(id))) continue
      ids.forEach((id) => used.add(id))
      const myStart = starters(mine.filter((id) => !t.give.includes(id)).concat(t.get), values, slots)
      const theirStart = starters(theirs.filter((id) => !t.get.includes(id)).concat(t.give), values, slots)
      all.push({ ...t, startsMine: t.get.filter((id) => myStart.has(id)), startsTheirs: t.give.filter((id) => theirStart.has(id)) })
      kept += 1
    }
  }
  const key = sort === 'balanced' ? (t) => Math.min(t.gainMine, t.gainTheirs) : (t) => t.gainMine
  return all.sort((a, b) => key(b) - key(a) || a.team.id - b.team.id).slice(0, limit)
}

export { GROUPS }
