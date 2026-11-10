import test from 'node:test'
import assert from 'node:assert/strict'
import { reachedNhl } from './prospectStatus.js'

test('an NHL regular season with a game played means the prospect has reached the NHL', () => {
  assert.equal(reachedNhl([{ league: 'OHL', game_type: 2, games: 60 }, { league: 'NHL', game_type: 2, games: 17 }]), true)
})

test('junior or minor-league rows, unplayed NHL rows and playoff-only NHL rows do not', () => {
  assert.equal(reachedNhl([{ league: 'OHL', game_type: 2, games: 60 }]), false)
  assert.equal(reachedNhl([{ league: 'NHL', game_type: 2, games: 0 }]), false)
  assert.equal(reachedNhl([{ league: 'NHL', game_type: 3, games: 4 }]), false)
})

test('no seasons at all is not in the NHL', () => {
  assert.equal(reachedNhl([]), false)
  assert.equal(reachedNhl(undefined), false)
})
