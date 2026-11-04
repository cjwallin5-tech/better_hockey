import assert from 'node:assert/strict'
import test from 'node:test'
import { pkDetail, pkRole } from './penaltyKill.js'

const base = { games_played: 15, sh_toi_per_game: 200, sh_toi_pct: 0.6 }

test('a player on the ice for most of the penalty kill is on the top unit', () => {
  assert.equal(pkRole(base).unit, 'PK1')
  assert.equal(pkRole({ ...base, sh_toi_pct: 0.5 }).unit, 'PK1')
})

test('a regular who is on for a third of it is on the second unit', () => {
  assert.equal(pkRole({ ...base, sh_toi_pct: 0.35 }).unit, 'PK2')
})

test('a few shifts is not a role', () => {
  assert.equal(pkRole({ ...base, sh_toi_pct: 0.25 }), null)
  assert.equal(pkRole({ ...base, sh_toi_per_game: 40 }), null)
  assert.equal(pkRole({ ...base, games_played: 3 }), null)
})

test('missing numbers give no role', () => {
  assert.equal(pkRole(null), null)
  assert.equal(pkRole({ games_played: 15 }), null)
  assert.equal(pkRole({ ...base, sh_toi_pct: null }), null)
})

test('the tooltip says the unit, the minutes and the share', () => {
  assert.equal(pkDetail(pkRole({ ...base, sh_toi_per_game: 222.25 })), "Top penalty-kill unit: 3:42 a game, on the ice for 60% of the team's penalty kill")
  assert.match(pkDetail(pkRole({ ...base, sh_toi_pct: 0.35 })), /^Second penalty-kill unit/)
})
