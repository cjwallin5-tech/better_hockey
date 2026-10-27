// Run with: npm test   (Node's built-in test runner; no extra packages)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { findTrades, lineupValue, starters } from './tradefinder.js'

const SLOTS = { C: 1, L: 1, R: 1, D: 1, G: 1 }
const val = (...rows) => new Map(rows.map(([id, group, value]) => [id, { group, value }]))
const team = (id, name, ...ids) => ({ id, name, players: ids.map((i) => ({ id: i })) })

test('only the best players in each group start, and a player at or below replacement adds nothing', () => {
  const values = val([1, 'C', 50], [2, 'C', 30], [3, 'L', 20], [4, 'L', -5], [5, 'D', 0])
  assert.deepEqual([...starters([1, 2, 3, 4, 5], values, SLOTS)].sort(), [1, 3])
  assert.equal(lineupValue([1, 2, 3, 4, 5], values, SLOTS), 70)
  assert.equal(lineupValue([1, 2], values, { C: 2 }), 80)
  assert.equal(lineupValue([], values, SLOTS), 0)
  assert.equal(lineupValue([99], values, SLOTS), 0)           // an unknown player adds nothing
})

test('a swap that fills each side\'s gap helps both: the surplus center for the surplus winger', () => {
  // me: two good centers (one starts), no winger; them: two good wingers (one starts), no center
  const values = val([1, 'C', 50], [2, 'C', 40], [3, 'L', 45], [4, 'L', 35])
  const out = findTrades({ mine: [1, 2], teams: [team(10, 'Them', 3, 4)], values, slots: SLOTS })
  const t = out[0]                                   // the best for me: my spare center for their best winger
  assert.deepEqual([t.give, t.get], [[2], [3]])
  assert.equal(t.gainMine, 45)                       // the winger starts for me, the spare center was worth nothing to me
  assert.equal(t.gainTheirs, 30)                     // they lose a 45 winger but their 35 winger moves up and the center starts: 75 against 45
  assert.deepEqual(t.startsMine, [3])
  assert.deepEqual(t.startsTheirs, [2])
  assert.equal(out.length, 2)                        // and a second, separate swap using the other two players
  const used = out.flatMap((x) => [...x.give, ...x.get])
  assert.equal(new Set(used).size, used.length)
})

test('a trade that only helps one side is dropped unless you ask for it', () => {
  // they have a good winger and no center need: they would only lose value
  const values = val([1, 'C', 50], [3, 'L', 45], [4, 'C', 60])
  const both = findTrades({ mine: [1], teams: [team(10, 'Them', 3, 4)], values, slots: SLOTS })
  assert.deepEqual(both, [])
  const mineOnly = findTrades({ mine: [1], teams: [team(10, 'Them', 3, 4)], values, slots: SLOTS, requireBoth: false })
  assert.ok(mineOnly.length > 0)
  assert.ok(mineOnly.every((t) => t.gainMine > 0))
})

test('players who do not add value are never offered, and nothing is suggested without a gain', () => {
  const values = val([1, 'C', 50], [2, 'C', -10], [3, 'L', 20], [4, 'L', -3])
  assert.deepEqual(findTrades({ mine: [1, 2], teams: [team(10, 'Them', 3, 4)], values, slots: SLOTS }), [])
})

test('reported gains are exactly the change in each side\'s lineup value, for every size of trade', () => {
  const values = val([1, 'C', 50], [2, 'C', 48], [3, 'L', 10], [4, 'L', 60], [5, 'L', 55], [6, 'C', 5], [7, 'R', 30], [8, 'R', 28])
  const slots = { C: 1, L: 1, R: 1 }
  const mine = [1, 2, 3, 7]
  const them = [4, 5, 6, 8]
  const out = findTrades({ mine, teams: [team(10, 'Them', ...them)], values, slots, perTeam: 50, limit: 100, requireBoth: false })
  assert.ok(out.length > 0)
  for (const t of out) {
    const mineAfter = [...mine.filter((id) => !t.give.includes(id)), ...t.get]
    const themAfter = [...them.filter((id) => !t.get.includes(id)), ...t.give]
    assert.ok(Math.abs(t.gainMine - (lineupValue(mineAfter, values, slots) - lineupValue(mine, values, slots))) < 1e-9)
    assert.ok(Math.abs(t.gainTheirs - (lineupValue(themAfter, values, slots) - lineupValue(them, values, slots))) < 1e-9)
    assert.ok(t.give.length + t.get.length <= 3)       // one-for-one, two-for-one or one-for-two
  }
})

test('when a smaller trade gains the same, it comes first', () => {
  // sending my spare center alone does everything sending him with a filler would
  const values = val([1, 'C', 50], [2, 'C', 40], [9, 'L', 1], [3, 'L', 45], [4, 'L', 35])
  const out = findTrades({ mine: [1, 2, 9], teams: [team(10, 'Them', 3, 4)], values, slots: SLOTS, perTeam: 1 })
  assert.equal(out[0].give.length + out[0].get.length, 2)
})

test('each team keeps a few non-overlapping suggestions, and sorting changes the order', () => {
  const values = val([1, 'C', 50], [2, 'C', 45], [3, 'C', 5], [11, 'L', 60], [12, 'L', 40], [13, 'R', 30], [14, 'R', 25])
  const slots = { C: 1, L: 1, R: 1 }
  const teams = [team(10, 'A', 11, 12, 13)]
  const out = findTrades({ mine: [1, 2, 3], teams, values, slots, perTeam: 3 })
  const used = out.flatMap((t) => [...t.give, ...t.get])
  assert.equal(new Set(used).size, used.length)          // no player appears twice
  assert.ok(out.length <= 3)
  const balanced = findTrades({ mine: [1, 2, 3], teams, values, slots, sort: 'balanced' })
  assert.ok(balanced.every((t, i, a) => i === 0 || Math.min(a[i - 1].gainMine, a[i - 1].gainTheirs) >= Math.min(t.gainMine, t.gainTheirs)))
})

test('teams with no players, and your own players on another team, are ignored', () => {
  const values = val([1, 'C', 50], [3, 'L', 45])
  assert.deepEqual(findTrades({ mine: [1], teams: [team(10, 'Empty')], values, slots: SLOTS }), [])
  assert.deepEqual(findTrades({ mine: [1], teams: [team(10, 'Dup', 1)], values, slots: SLOTS }), [])
})
