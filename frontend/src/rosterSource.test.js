import test from 'node:test'
import assert from 'node:assert/strict'
import { rosterSource } from './rosterSource.js'

const A = { id: 1, kind: 'skater', name: 'A' }
const league = (own, players = []) => ({ id: 7, name: 'Friends', teams: [{ id: 1, mine: false, own_roster: false, players: [] }, { id: 2, mine: true, own_roster: own, players }] })

test('signed out: the personal roster, nothing to start', () => {
  assert.deepEqual(rosterSource({ signedIn: false, status: 'off', active: null }), { kind: 'personal', needsStart: false, leagueName: null })
})

test('signed in and still loading: nothing may be changed yet', () => {
  assert.equal(rosterSource({ signedIn: true, status: 'loading', active: null }).kind, 'loading')
  assert.equal(rosterSource({ signedIn: true, status: 'off', active: null }).kind, 'loading')
})

test('no league active: the personal roster', () => {
  assert.deepEqual(rosterSource({ signedIn: true, status: 'ready', active: null }), { kind: 'personal', needsStart: false, leagueName: null })
})

test('a league whose team has its own roster: that roster, even when it is empty', () => {
  assert.deepEqual(rosterSource({ signedIn: true, status: 'ready', active: league(true, [A]) }), { kind: 'league', id: 7, name: 'Friends', players: [A] })
  assert.deepEqual(rosterSource({ signedIn: true, status: 'ready', active: league(true, []) }).players, [])
})

test('a league whose team has no roster of its own yet: personal roster, and it needs starting', () => {
  assert.deepEqual(rosterSource({ signedIn: true, status: 'ready', active: league(false) }), { kind: 'personal', needsStart: true, leagueName: 'Friends' })
})

test('a failed league load falls back to the personal roster', () => {
  assert.equal(rosterSource({ signedIn: true, status: 'error', active: null }).kind, 'personal')
})
