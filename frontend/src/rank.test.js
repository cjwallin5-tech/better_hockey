import test from 'node:test'
import assert from 'node:assert/strict'
import { ordinal, placeLabel, placesFor } from './rank.js'

const rows = (...goals) => goals.map((goals, i) => ({ id: i, goals }))

test('ordinals handle the teens', () => {
  assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21, 22, 103].map(ordinal), ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd', '103rd'])
})

test('a shared rank shows T- in front', () => {
  assert.equal(placeLabel({ rank: 5, tied: true }), 'T-5th')
  assert.equal(placeLabel({ rank: 5, tied: false }), '5th')
})

test('players level on a value all share the first place and are all tied; the next player skips the places used', () => {
  const p = placesFor(rows(11, 11, 11, 9, 8, 8, 5), 'goals')
  assert.deepEqual(p.map((x) => x.rank), [1, 1, 1, 4, 5, 5, 7])
  assert.deepEqual(p.map((x) => x.tied), [true, true, true, false, true, true, false])
})

test('an ascending sort ties the same way', () => {
  const p = placesFor(rows(1, 2, 2, 3), 'goals')
  assert.deepEqual(p.map((x) => [x.rank, x.tied]), [[1, false], [2, true], [2, true], [4, false]])
})

test('missing values and text columns are never tied', () => {
  assert.deepEqual(placesFor([{ n: null }, { n: null }], 'n'), [{ rank: 1, tied: false }, { rank: 2, tied: false }])
  assert.deepEqual(placesFor([{ name: 'A' }, { name: 'A' }], 'name'), [{ rank: 1, tied: false }, { rank: 2, tied: false }])
})

test('values that differ by rounding noise are the same value', () => {
  assert.equal(placesFor(rows(0.1 + 0.2, 0.3), 'goals')[0].tied, true)
})

test('an empty or one-row list is fine', () => {
  assert.deepEqual(placesFor([], 'goals'), [])
  assert.deepEqual(placesFor(rows(4), 'goals'), [{ rank: 1, tied: false }])
})
