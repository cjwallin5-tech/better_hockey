// Run with: npm test   (Node's built-in test runner; no extra packages)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { buildBoard, keeperRows, myPicks, needs, recommend, roundOf, roundValue, slotAt, tierCliffs, tierGroup } from './draft.js'

const row = (id, value, group = 'C') => ({ id, value, group })

test('tiers: a big drop starts a new tier, small steps do not', () => {
  const out = tierGroup([row(1, 100), row(2, 98), row(3, 96), row(4, 60), row(5, 58), row(6, 20)], 6)
  assert.deepEqual(out.map((r) => [r.id, r.tier]), [[1, 1], [2, 1], [3, 1], [4, 2], [5, 2], [6, 3]])
})

test('tiers: input order does not matter and an empty or single group is fine', () => {
  assert.deepEqual(tierGroup([row(2, 5), row(1, 9)], 2).map((r) => r.id), [1, 2])
  assert.deepEqual(tierGroup([], 3), [])
  assert.deepEqual(tierGroup([row(1, 4)], 3), [{ id: 1, value: 4, group: 'C', tier: 1 }])
})

test('board: best first across positions, with group rank, overall rank and tier', () => {
  const values = new Map([[1, { value: 50, group: 'C' }], [2, { value: 80, group: 'D' }], [3, { value: 30, group: 'C' }], [9, { value: 99, group: 'C' }]])
  const info = new Map([[1, { name: 'A' }], [2, { name: 'B' }], [3, { name: 'C' }]])  // 9 is unknown and left out
  const board = buildBoard({ values, info, league: { teams: 2, slots: { C: 1, L: 1, R: 1, D: 1, G: 1 } } })
  assert.deepEqual(board.map((r) => [r.id, r.overall, r.groupRank]), [[2, 1, 1], [1, 2, 1], [3, 3, 2]])
  assert.equal(board[0].name, 'B')
})

test('snake order reverses every other round; straight order does not', () => {
  assert.deepEqual([1, 2, 3, 4, 5, 6].map((n) => slotAt(n, 3)), [1, 2, 3, 3, 2, 1])
  assert.deepEqual([1, 2, 3, 4, 5, 6].map((n) => slotAt(n, 3, false)), [1, 2, 3, 1, 2, 3])
  assert.equal(roundOf(1, 12), 1)
  assert.equal(roundOf(13, 12), 2)
})

test('my next picks in a snake draft', () => {
  assert.deepEqual(myPicks({ slot: 3, teams: 3, count: 3 }), [3, 4, 9])
  assert.deepEqual(myPicks({ slot: 1, teams: 4, from: 2, count: 2 }), [8, 9])
  assert.deepEqual(myPicks({ slot: 2, teams: 3, snake: false, from: 3, count: 2 }), [5, 8])
})

test('needs: open starting slots after my picks, never negative', () => {
  const slots = { C: 2, L: 1, R: 1, D: 2, G: 1 }
  assert.deepEqual(needs(['C', 'C', 'C', 'D'], slots), { C: 0, L: 1, R: 1, D: 1, G: 1 })
})

test('recommend: best overall, and the best at a position still open', () => {
  const available = [{ id: 1, group: 'C' }, { id: 2, group: 'C' }, { id: 3, group: 'D' }]
  const r = recommend(available, { C: 0, D: 1 })
  assert.equal(r.best.id, 1)
  assert.equal(r.forNeed.id, 3)
  assert.equal(recommend(available, { C: 0, D: 0 }).forNeed.id, 1)
  assert.deepEqual(recommend([], {}), { best: null, forNeed: null })
})

test('tier cliffs: players left in the top tier and the drop to the next', () => {
  const available = tierGroup([row(1, 100), row(2, 99), row(3, 50)], 3)
  const c = tierCliffs(available).C
  assert.equal(c.tier, 1)
  assert.equal(c.left, 2)
  assert.equal(c.drop, 50)
  assert.equal(tierCliffs(available).G, undefined)
})

test('round value is the value at the middle of the round; keepers need a surplus over it', () => {
  const board = Array.from({ length: 30 }, (_, i) => ({ id: i + 1, value: 100 - i * 3 }))   // 100, 97, 94, ...
  assert.equal(roundValue(board, 1, 4), board[1].value)        // pick 2 of 4
  assert.equal(roundValue(board, 2, 4), board[5].value)        // pick 6
  assert.equal(roundValue(board, 99, 4), board[29].value)      // past the end: the last player
  const rows = keeperRows([{ id: 1, round: 5 }, { id: 10, round: 1 }, { id: 3, round: 2 }, { id: 99, round: 1 }], board, 4, 2)
  assert.deepEqual(rows.map((r) => [r.id, r.keep]), [[1, true], [3, true], [10, false]])   // 99 is unknown; 10 is worth less than a round-1 pick
  assert.ok(rows[0].surplus > rows[1].surplus)
})

test('keepers: the cap on how many to keep applies, and a player with no surplus is never kept', () => {
  const board = Array.from({ length: 20 }, (_, i) => ({ id: i + 1, value: 100 - i * 5 }))
  const rows = keeperRows([{ id: 1, round: 8 }, { id: 2, round: 8 }, { id: 3, round: 8 }], board, 2, 1)
  assert.deepEqual(rows.map((r) => r.keep), [true, false, false])
  assert.equal(keeperRows([{ id: 20, round: 1 }], board, 2, 3)[0].keep, false)
})
