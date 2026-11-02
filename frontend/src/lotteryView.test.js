import test from 'node:test'
import assert from 'node:assert/strict'
import { SORTS, chance, ordinal, shade, visibleTeams } from './lotteryView.js'

test('chances read as percentages with small ones flagged', () => {
  assert.equal(chance(0.255), '26%')
  assert.equal(chance(0.002), '<1%')
  assert.equal(chance(0), '')
  assert.equal(chance(null), '')
  assert.equal(chance(0.1234, 1), '12.3%')
})

test('only teams with a real lottery chance are listed unless all are asked for', () => {
  const teams = [{ in_lottery: 0.9 }, { in_lottery: 0.01 }, { in_lottery: 0.02 }]
  assert.equal(visibleTeams(teams, false).length, 2)
  assert.equal(visibleTeams(teams, true).length, 3)
})

test('heat cells scale with the chance and cap out', () => {
  assert.equal(shade(0), 0)
  assert.equal(shade(0.004), 0)
  assert.equal(shade(0.2), 35)
  assert.equal(shade(0.9), 70)
})

test('ordinals handle the teens', () => {
  assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21].map(ordinal), ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st'])
})

test('sorts put the likeliest first and the lowest points first', () => {
  const rows = [{ first_overall: 0.1, points: 20 }, { first_overall: 0.2, points: 10 }]
  assert.deepEqual([...rows].sort((a, b) => SORTS.first_overall(a) - SORTS.first_overall(b)).map((r) => r.points), [10, 20])
  assert.deepEqual([...rows].sort((a, b) => SORTS.points(a) - SORTS.points(b)).map((r) => r.points), [10, 20])
})
