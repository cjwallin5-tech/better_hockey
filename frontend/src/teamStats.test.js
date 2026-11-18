import test from 'node:test'
import assert from 'node:assert/strict'
import { leagueRanks, sortByStat, statById, statValue } from './teamStats.js'

const teams = [
  { abbrev: 'AAA', goals_against_pg: 3.1, pp_pct: 0.2, games_played: 10, goal_diff: 5 },
  { abbrev: 'BBB', goals_against_pg: 2.4, pp_pct: 0.3, games_played: 10, goal_diff: -10 },
  { abbrev: 'CCC', goals_against_pg: null, pp_pct: 0.3, games_played: 0, goal_diff: 0 },
]

test('sorts best first, lowest first for stats where less is better, missing last', () => {
  assert.deepEqual(sortByStat(statById('goals_against_pg'), teams).map((t) => t.abbrev), ['BBB', 'AAA', 'CCC'])
  assert.deepEqual(sortByStat(statById('pp_pct'), teams).map((t) => t.abbrev), ['BBB', 'CCC', 'AAA'])
})

test('league ranks share a rank on ties and skip teams without the stat', () => {
  const r = leagueRanks(statById('pp_pct'), teams)
  assert.equal(r.get('BBB'), 1)
  assert.equal(r.get('CCC'), 1)
  assert.equal(r.get('AAA'), 3)
  assert.equal(leagueRanks(statById('goals_against_pg'), teams).has('CCC'), false)
})

test('reads figures from a separate source by team abbreviation', () => {
  const stat = statById('pk_xga60')
  assert.equal(statValue(stat, teams[0], { AAA: { pk_xga60: 8.5 } }), 8.5)
  assert.equal(statValue(stat, teams[1], { AAA: { pk_xga60: 8.5 } }), null)
})

test('goal differential is per game', () => {
  assert.equal(statValue(statById('goal_diff_pg'), teams[0]), 0.5)
  assert.equal(statValue(statById('goal_diff_pg'), teams[2]), null)
})
