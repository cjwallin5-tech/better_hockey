import test from 'node:test'
import assert from 'node:assert/strict'
import { hasLeague, hasScoring, leagueShape, planReconcile, sameLeague, sameState } from './syncPlan.js'

test('leagueShape turns numbers saved as text into numbers and keeps only the synced fields', () => {
  const shape = leagueShape({ teams: '14', format: 'points', slots: { C: '2', D: 4 }, categories: { skater: ['goals'] } })
  assert.deepEqual(shape, { teams: 14, format: 'points', slots: { C: 2, D: 4 } })
  assert.deepEqual(leagueShape({}), { teams: undefined, format: undefined, slots: undefined })
  assert.deepEqual(leagueShape(undefined), { teams: undefined, format: undefined, slots: undefined })
})

const mcd = { id: 8478402, kind: 'skater', name: 'Connor McDavid' }
const LEAGUE = { teams: 24, format: 'categories', slots: { C: 2, D: 5, G: 2, L: 2, R: 2 } }
const state = (over = {}) => ({ players: [], scoring: {}, league: {}, ...over })

test('hasLeague is false for nothing saved and true for any saved setting', () => {
  assert.equal(hasLeague({}), false)
  assert.equal(hasLeague(undefined), false)
  assert.equal(hasLeague({ teams: undefined, format: undefined, slots: undefined }), false)
  assert.equal(hasLeague({ teams: 12 }), true)
  assert.equal(hasLeague(LEAGUE), true)
})

test('sameLeague ignores slot order and numbers typed as text', () => {
  const local = { teams: '24', format: 'categories', slots: { C: 2, L: 2, R: 2, D: '5', G: 2 } }
  assert.equal(sameLeague(LEAGUE, local), true)
  assert.equal(sameLeague(LEAGUE, { ...local, teams: '14' }), false)
  assert.equal(sameLeague(LEAGUE, { ...local, format: 'points' }), false)
})

test('a device with the roster but no league settings does not wipe the account league', () => {
  const server = state({ players: [mcd], league: LEAGUE })
  const mine = state({ players: [mcd] })
  assert.deepEqual(planReconcile(server, mine), { roster: 'none', league: 'download', scoring: 'none' })
})

test('an account with settings but no roster still gives them to a fresh device', () => {
  assert.deepEqual(planReconcile(state({ league: LEAGUE }), state()), { roster: 'none', league: 'download', scoring: 'none' })
})

test('a device with settings uploads them only when the account has none', () => {
  assert.deepEqual(planReconcile(state({ players: [mcd] }), state({ players: [mcd], league: LEAGUE })), { roster: 'none', league: 'upload', scoring: 'none' })
  assert.deepEqual(planReconcile(state(), state({ league: LEAGUE })), { roster: 'none', league: 'upload', scoring: 'none' })
})

test('when both have different settings the account wins, wherever the roster stands', () => {
  const other = { ...LEAGUE, teams: 10 }
  assert.deepEqual(planReconcile(state({ players: [mcd], league: LEAGUE }), state({ players: [mcd], league: other })), { roster: 'none', league: 'download', scoring: 'none' })
  assert.deepEqual(planReconcile(state({ league: LEAGUE }), state({ players: [mcd], league: other })).league, 'download')
})

test('matching settings, in a different key order, need nothing', () => {
  const local = { teams: 24, format: 'categories', slots: { C: 2, L: 2, R: 2, D: 5, G: 2 } }
  assert.deepEqual(planReconcile(state({ players: [mcd], league: LEAGUE }), state({ players: [mcd], league: local })), { roster: 'none', league: 'none', scoring: 'none' })
})

test('roster rules are unchanged: upload, download, conflict', () => {
  assert.equal(planReconcile(state(), state({ players: [mcd] })).roster, 'upload')
  assert.equal(planReconcile(state({ players: [mcd] }), state()).roster, 'download')
  const other = { id: 1, kind: 'goalie', name: 'Someone' }
  assert.equal(planReconcile(state({ players: [mcd] }), state({ players: [other] })).roster, 'conflict')
  assert.equal(planReconcile(state({ players: [mcd], scoring: { goals: 1 } }), state({ players: [mcd], scoring: { goals: 2 } })).roster, 'conflict')
})

test('both sides empty: nothing to do', () => {
  assert.deepEqual(planReconcile(state(), state()), { roster: 'none', league: 'none', scoring: 'none' })
})

const DEFAULT_SCORING = { goals: 1, assists: 1 }

test('hasScoring: an empty object means nothing saved', () => {
  assert.equal(hasScoring({}), false)
  assert.equal(hasScoring(undefined), false)
  assert.equal(hasScoring(DEFAULT_SCORING), true)
})

test('an account with no scoring saved does not differ from this browser\'s scoring', () => {
  assert.equal(sameState(state({ players: [mcd] }), state({ players: [mcd], scoring: DEFAULT_SCORING })), true)
  assert.equal(sameState(state(), state({ scoring: DEFAULT_SCORING })), true)
})

test('saved scoring that differs is still a difference, and so is a different roster', () => {
  assert.equal(sameState(state({ scoring: { goals: 3 } }), state({ scoring: DEFAULT_SCORING })), false)
  assert.equal(sameState(state({ players: [mcd] }), state()), false)
})

test('a fresh account with this browser on default scoring uploads it instead of conflicting or being blanked', () => {
  assert.deepEqual(planReconcile(state(), state({ scoring: DEFAULT_SCORING })), { roster: 'none', league: 'none', scoring: 'upload' })
  // same roster on both sides, account never saved scoring: no conflict
  assert.deepEqual(planReconcile(state({ players: [mcd] }), state({ players: [mcd], scoring: DEFAULT_SCORING })), { roster: 'none', league: 'none', scoring: 'upload' })
})

test('once the account has scoring nothing is uploaded for it', () => {
  assert.equal(planReconcile(state({ scoring: DEFAULT_SCORING }), state({ scoring: DEFAULT_SCORING })).scoring, 'none')
  assert.equal(planReconcile(state({ scoring: { goals: 3 } }), state({ scoring: DEFAULT_SCORING })).scoring, 'none')
})
