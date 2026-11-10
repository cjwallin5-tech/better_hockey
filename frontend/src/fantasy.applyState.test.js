import test from 'node:test'
import assert from 'node:assert/strict'

// fantasy.js reads the browser's localStorage and window; stand in for both.
const store = new Map()
globalThis.localStorage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) }
globalThis.window = { dispatchEvent: () => true, addEventListener: () => {}, removeEventListener: () => {} }
const { applyState, readScoring } = await import('./fantasy.js')

const mcd = { id: 8478402, kind: 'skater', name: 'Connor McDavid' }

test('applying an account that has no scoring saved keeps this browser\'s scoring', () => {
  store.clear()
  store.set('nhl-stats.fantasy-scoring', JSON.stringify({ goals: 3, assists: 2 }))
  applyState({ players: [mcd], scoring: {}, league: {} })
  assert.deepEqual(readScoring(), { goals: 3, assists: 2 })
  applyState({ players: [mcd], league: {} })   // scoring missing altogether
  assert.deepEqual(readScoring(), { goals: 3, assists: 2 })
})

test('applying an account that has scoring saved takes it', () => {
  store.clear()
  store.set('nhl-stats.fantasy-scoring', JSON.stringify({ goals: 3 }))
  applyState({ players: [], scoring: { goals: 1, hits: 0.5 }, league: {} })
  assert.deepEqual(readScoring(), { goals: 1, hits: 0.5 })
})

test('with nothing stored here and nothing on the account, scoring stays at the default rather than going blank', () => {
  store.clear()
  applyState({ players: [], scoring: {}, league: {} })
  assert.deepEqual(readScoring(), { goals: 1, assists: 1 })
})
