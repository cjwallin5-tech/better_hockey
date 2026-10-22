import test from 'node:test'
import assert from 'node:assert/strict'
import { trophyKey } from './trophies.js'

test('curly quotes, straight quotes and case all match', () => {
  assert.equal(trophyKey('Maurice “Rocket” Richard Trophy'), trophyKey('maurice "rocket" richard trophy'))
  assert.equal(trophyKey('Presidents’ Trophy'), 'presidentstrophy')
})

test('a missing name gives an empty key', () => {
  assert.equal(trophyKey(undefined), '')
})
