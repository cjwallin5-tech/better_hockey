// Run with: npm test   (Node's built-in test runner; no extra packages)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { tradeIdeas } from './tradeIdeas.js'

const v = (value, group = 'C') => ({ value, group })
const l = (flag, z, enough = true) => ({ flag, z, enough })

const values = new Map([
  [1, v(20)], [2, v(10)], [3, v(25)], [4, v(5)], [5, v(18)], [6, v(30, 'D')], [7, v(22)], [8, v(-3)],
])
const luck = new Map([
  [1, l('hot', 2.4)], [2, l('hot', 1.6)], [3, l('cold', -1.9)], [4, l('cold', -2.5)],
  [5, l('cold', -1.6)], [6, l('cold', -2)], [7, l('cold', -1.7, false)], [8, l('cold', -2)],
])

test('sell lists your hot players, hottest first, with same-position cold targets of similar value', () => {
  const { sell } = tradeIdeas({ values, luck, roster: new Set([1, 2]) })
  assert.deepEqual(sell.map((s) => s.id), [1, 2])
  // player 1 is worth 20: targets must be cold, unowned, same position, worth at least 90% (18)
  assert.deepEqual(sell[0].targets.map((t) => t.id), [3, 5])
  // player 2 is worth 10: 4 is too low (5), 3 and 5 qualify
  assert.deepEqual(sell[1].targets.map((t) => t.id), [3, 5])
})

test('buy lists unowned cold players with positive value, best first, skipping small samples', () => {
  const { buy } = tradeIdeas({ values, luck, roster: new Set([1]) })
  assert.deepEqual(buy.map((b) => b.id), [6, 3, 5, 4]) // 7 has too small a sample, 8 has negative value
})

test('owned cold players are not buy targets, and steady or unknown players are ignored', () => {
  const steady = new Map([...luck, [1, l('steady', 0.2)]])
  const { sell, buy } = tradeIdeas({ values, luck: steady, roster: new Set([1, 3]) })
  assert.deepEqual(sell, [])
  assert.ok(!buy.some((b) => b.id === 3))
  assert.deepEqual(tradeIdeas({ values, luck: new Map(), roster: new Set([1]) }), { sell: [], buy: [] })
})

test('a hot player with no value is not a sell candidate', () => {
  const { sell } = tradeIdeas({ values: new Map([[1, v(-2)]]), luck: new Map([[1, l('hot', 2)]]), roster: new Set([1]) })
  assert.deepEqual(sell, [])
})
