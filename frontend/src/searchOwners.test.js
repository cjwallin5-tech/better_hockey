import test from 'node:test'
import assert from 'node:assert/strict'
import { markOwners } from './searchOwners.js'

const rows = [{ player_id: 1, name: 'A' }, { player_id: 2, name: 'B' }, { player_id: 3, name: 'C' }, { player_id: 4, name: 'D' }]

test('with no league the rows are returned as they came', () => {
  assert.equal(markOwners(rows, null), rows)
})

test('each row says who holds the player, or null', () => {
  const out = markOwners(rows, new Map([[2, 'Owner FC'], [4, 'Friends']]))
  assert.deepEqual(out.map((r) => [r.player_id, r.ownedBy]), [[1, null], [3, null], [2, 'Owner FC'], [4, 'Friends']])
})

test('available players come first and keep their order, as do the owned ones', () => {
  const out = markOwners(rows, new Map([[1, 'X'], [3, 'Y']]))
  assert.deepEqual(out.map((r) => r.player_id), [2, 4, 1, 3])
})

test('nobody owned means the same order with a null owner on every row', () => {
  const out = markOwners(rows, new Map())
  assert.deepEqual(out.map((r) => r.player_id), [1, 2, 3, 4])
  assert.ok(out.every((r) => r.ownedBy === null))
})

test('the original rows are not changed', () => {
  markOwners(rows, new Map([[1, 'X']]))
  assert.equal('ownedBy' in rows[0], false)
})

test('an empty list stays empty', () => {
  assert.deepEqual(markOwners([], new Map([[1, 'X']])), [])
})
