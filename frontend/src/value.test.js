// Run with: npm test   (Node's built-in test runner; no extra packages)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { SKATER_CATEGORIES } from './categoryDefs.js'
import { GROUPS, PRIOR_WEIGHT, cleanLeague, groupOf, playerValues, shrink, teamOf, tradeSummary } from './value.js'

const GOALS = { goals: 1 }   // scoring: one point per goal
const sk = (id, goals, gp, extra = {}) => ({ player_id: id, position: 'C', team: 'AAA', games_played: gp, goals, ...extra })
const league = (teams, slots) => ({ teams, slots: { C: 0, L: 0, R: 0, D: 0, G: 0, ...slots } })
const statPriorOf = (key) => SKATER_CATEGORIES.find((d) => d.key === key).prior
const near = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} is not within ${eps} of ${b}`)

test('shrink pulls a short sample toward the mean', () => {
  near(shrink(10, 10, 0.5, 20), (10 + 20 * 0.5) / 30)
  near(shrink(0, 0, 0.5, 20), 0.5)            // no games at all: just the mean
  near(shrink(100, 100, 0.5, 0.0001), 1, 1e-4) // a huge sample ignores the prior
})

test('groups and teams', () => {
  assert.equal(groupOf({ position: 'D' }, 'skater'), 'D')
  assert.equal(groupOf({ position: 'L' }, 'skater'), 'L')
  assert.equal(groupOf({ position: 'G' }, 'goalie'), 'G')
  assert.equal(groupOf({ position: 'W' }, 'skater'), 'C')   // an unknown label doesn't break anything
  assert.equal(teamOf({ team: 'TOR,EDM' }), 'EDM')
  assert.equal(teamOf({ team: null }), '')
})

test('cleanLeague bounds and defaults', () => {
  assert.equal(cleanLeague({}).teams, 12)
  assert.equal(cleanLeague({ teams: 100 }).teams, 32)
  assert.equal(cleanLeague({ teams: 1 }).teams, 2)
  assert.equal(cleanLeague({ teams: '10' }).teams, 10)
  assert.equal(cleanLeague({ slots: { C: -3, D: '5' } }).slots.C, 0)
  assert.equal(cleanLeague({ slots: { C: -3, D: '5' } }).slots.D, 5)
  assert.deepEqual(Object.keys(cleanLeague(null).slots), GROUPS)
})

test('replacement level is the first player who would not start, and is worth zero', () => {
  // 2 teams x 1 center slot = 2 starters, so the third-best center is replacement level
  const skaters = [sk(1, 20, 10), sk(2, 16, 10), sk(3, 10, 10), sk(4, 4, 10)]
  const v = playerValues({ skaters, goalies: [], scoring: GOALS, league: league(2, { C: 1 }) })
  assert.equal(v.get(1).groupRank, 1)
  assert.equal(v.get(3).replacement, v.get(3).shrunk)
  near(v.get(3).value, 0)
  assert.ok(v.get(1).value > v.get(2).value && v.get(2).value > 0)
  assert.ok(v.get(4).value < 0, 'below replacement is negative')
})

test('a position is only compared with its own position', () => {
  const skaters = [
    sk(1, 20, 10), sk(2, 10, 10),
    sk(3, 6, 10, { position: 'D' }), sk(4, 2, 10, { position: 'D' }),
  ]
  const v = playerValues({ skaters, goalies: [], scoring: GOALS, league: league(1, { C: 1, D: 1 }) })
  // each group has one starter, so the second player in each is replacement
  near(v.get(2).value, 0)
  near(v.get(4).value, 0)
  assert.ok(v.get(3).value > 0, 'the best defenseman has value even though a center scores more')
})

test('goalies are valued against goalies using goalie scoring', () => {
  const goalies = [
    { player_id: 10, team: 'AAA', games_played: 8, wins: 6 },
    { player_id: 11, team: 'AAA', games_played: 8, wins: 3 },
  ]
  const v = playerValues({ skaters: [sk(1, 20, 10)], goalies, scoring: { wins: 4, goals: 1 }, league: league(1, { G: 1, C: 1 }) })
  assert.equal(v.get(10).group, 'G')
  assert.ok(v.get(10).value > 0)
  near(v.get(11).value, 0)
})

test('value scales with games left and with how often the player plays', () => {
  const skaters = [sk(1, 10, 10, { team: 'AAA' }), sk(2, 10, 10, { team: 'BBB' }), sk(3, 2, 10, { team: 'AAA' })]
  const gamesLeft = { AAA: { played: 10, left: 70 }, BBB: { played: 10, left: 35 } }
  const v = playerValues({ skaters, goalies: [], scoring: GOALS, league: league(1, { C: 1 }), gamesLeft })
  near(v.get(1).above, v.get(2).above)
  near(v.get(1).value / v.get(2).value, 2)
  // plays half of the team's games so far: expect half of the games left
  const half = playerValues({ skaters: [sk(1, 5, 5, { team: 'AAA' }), sk(3, 2, 10, { team: 'AAA' })], goalies: [], scoring: GOALS,
    league: league(1, { C: 1 }), gamesLeft })
  near(half.get(1).playShare, 0.5)
  near(half.get(1).expectedGames, 35)
})

test('without a schedule the season length stands in for games left', () => {
  const v = playerValues({ skaters: [sk(1, 10, 10), sk(2, 1, 10)], goalies: [], scoring: GOALS, league: league(1, { C: 1 }), gamesPerSeason: 84 })
  assert.equal(v.get(1).gamesLeft, 74)
})

test('a short hot streak is pulled back toward the average', () => {
  const regulars = Array.from({ length: 10 }, (_, i) => sk(100 + i, 5, 10))      // 0.5 points a game
  const hot = sk(1, 6, 3)                                                         // 2.0 a game over 3 games
  const v = playerValues({ skaters: [hot, ...regulars], goalies: [], scoring: GOALS, league: league(1, { C: 1 }) })
  assert.equal(v.get(1).rate, 2)
  assert.ok(v.get(1).shrunk < 0.9 && v.get(1).shrunk > 0.5)   // 2.0 a game raw, about 0.85 once pulled toward 0.5
  near(v.get(1).shrunk, shrink(6, 3, 0.5, PRIOR_WEIGHT.noHistory))
})

test('goals and assists are pulled toward the player\'s own record, not the position average', () => {
  // everyone else scores 0.5 a game; this player has a 1.5-a-game record but a slow 5-game start (2 points)
  const regulars = Array.from({ length: 10 }, (_, i) => sk(100 + i, 0, 10, { assists: 5 }))
  const slow = sk(1, 1, 5, { assists: 1 })
  const priors = { 1: { goals: 0.5, assists: 1.0 } }
  const v = playerValues({ skaters: [slow, ...regulars], goalies: [], scoring: { goals: 1, assists: 1 }, league: league(1, { C: 1 }), priors })
  near(v.get(1).shrunk, (2 + PRIOR_WEIGHT.history * 1.5) / (5 + PRIOR_WEIGHT.history))
  assert.equal(v.get(1).hasHistory, true)
  // the same start with no record is pulled toward the average instead, much further down
  const none = playerValues({ skaters: [slow, ...regulars], goalies: [], scoring: { goals: 1, assists: 1 }, league: league(1, { C: 1 }) })
  assert.equal(none.get(1).hasHistory, false)
  assert.ok(none.get(1).shrunk < v.get(1).shrunk)
})

test('a record is weighted by your scoring: goals and assists can be worth different amounts', () => {
  const regulars = Array.from({ length: 6 }, (_, i) => sk(100 + i, 5, 10, { assists: 5 }))
  const priors = { 1: { goals: 1.0, assists: 0.0 } }
  const player = sk(1, 0, 4, { assists: 0 })
  const goalsOnly = playerValues({ skaters: [player, ...regulars], goalies: [], scoring: { goals: 3 }, league: league(1, { C: 1 }), priors })
  const assistsOnly = playerValues({ skaters: [player, ...regulars], goalies: [], scoring: { assists: 3 }, league: league(1, { C: 1 }), priors })
  near(goalsOnly.get(1).shrunk, (0 + PRIOR_WEIGHT.history * 3) / (4 + PRIOR_WEIGHT.history))   // a goal scorer's record counts
  assert.ok(assistsOnly.get(1).shrunk < goalsOnly.get(1).shrunk)                                // but it is worth nothing here
})

test('other stats are pulled toward the position average by that stat\'s own weight', () => {
  const regulars = Array.from({ length: 6 }, (_, i) => sk(100 + i, 0, 10, { hits: 10 }))      // 1 hit a game
  const player = sk(1, 0, 5, { hits: 20 })                                                      // 4 hits a game early
  const v = playerValues({ skaters: [player, ...regulars], goalies: [], scoring: { hits: 1 }, league: league(1, { C: 1 }) })
  // the position average counts everyone who plays regularly, this player included: (6 x 10 + 20) hits over (60 + 5) games
  near(v.get(1).shrunk, shrink(20, 5, 80 / 65, statPriorOf('hits')))
})

test('a noisy stat is pulled much harder than a steady one', () => {
  // the same early surge in plus/minus and in hits: 10 over 5 games against a league average of about 0.15 a game
  const regulars = (key) => Array.from({ length: 6 }, (_, i) => sk(100 + i, 0, 10, { [key]: 0 }))
  const surge = (key) => playerValues({ skaters: [sk(1, 0, 5, { [key]: 10 }), ...regulars(key)], goalies: [], scoring: { [key]: 1 }, league: league(1, { C: 1 }) }).get(1)
  const pm = surge('plus_minus')
  const hits = surge('hits')
  assert.ok(pm.shrunk < hits.shrunk, `plus/minus ${pm.shrunk} should be pulled further toward average than hits ${hits.shrunk}`)
  near(pm.shrunk, shrink(10, 5, 10 / 65, statPriorOf('plus_minus')))
  assert.ok(statPriorOf('plus_minus') > statPriorOf('hits'))
})

test('a stat your scoring does not count has no effect on value', () => {
  const regulars = Array.from({ length: 6 }, (_, i) => sk(100 + i, 5, 10, { hits: 10 }))
  const a = playerValues({ skaters: [sk(1, 5, 10, { hits: 90 }), ...regulars], goalies: [], scoring: { goals: 1 }, league: league(1, { C: 1 }) })
  const b = playerValues({ skaters: [sk(1, 5, 10, { hits: 0 }), ...regulars], goalies: [], scoring: { goals: 1 }, league: league(1, { C: 1 }) })
  near(a.get(1).shrunk, b.get(1).shrunk)
})

test('players with no games are left out, and zero scoring values everyone at zero', () => {
  const v = playerValues({ skaters: [sk(1, 5, 0), sk(2, 5, 10), sk(3, 1, 10)], goalies: [], scoring: {}, league: league(1, { C: 1 }) })
  assert.equal(v.has(1), false)
  assert.equal(v.get(2).value, 0)
  assert.equal(v.get(3).value, 0)
})

test('overall rank orders by value across positions', () => {
  const skaters = [sk(1, 20, 10), sk(2, 10, 10), sk(3, 8, 10, { position: 'D' }), sk(4, 2, 10, { position: 'D' })]
  const v = playerValues({ skaters, goalies: [], scoring: GOALS, league: league(1, { C: 1, D: 1 }) })
  const order = [...v.values()].sort((a, b) => a.overallRank - b.overallRank).map((p) => p.id)
  assert.equal(order[0], 1)
  assert.deepEqual(new Set([...v.values()].map((p) => p.overallRank)).size, 4)
})

test('a trade: values on each side and the net', () => {
  const skaters = [sk(1, 20, 10), sk(2, 14, 10), sk(3, 8, 10), sk(4, 2, 10)]
  const v = playerValues({ skaters, goalies: [], scoring: GOALS, league: league(1, { C: 2 }) })
  const t = tradeSummary([2], [1], v)
  near(t.net, v.get(1).value - v.get(2).value)
  assert.ok(t.net > 0)
  assert.deepEqual(t.give.missing, [])
  // two-for-one: the open slot is replacement level, worth zero
  const two = tradeSummary([2, 3], [1], v)
  near(two.give.value, v.get(2).value + v.get(3).value)
  near(two.net, v.get(1).value - two.give.value)
})

test('trade with an unknown player counts it as zero and says so', () => {
  const v = playerValues({ skaters: [sk(1, 20, 10), sk(2, 5, 10)], goalies: [], scoring: GOALS, league: league(1, { C: 1 }) })
  const t = tradeSummary([999], [1], v)
  assert.deepEqual(t.give.missing, [999])
  near(t.net, v.get(1).value)
})
