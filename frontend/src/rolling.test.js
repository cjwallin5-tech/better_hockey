// Run with: npm test   (Node's built-in test runner; no extra packages)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { goalieForm, lastN, missingScoring, rollingMean, rollingRatio, skaterForm, windowsFor } from './rolling.js'

const near = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} is not within ${eps} of ${b}`)
const game = (points, extra = {}) => ({ goals: 0, assists: points, points, shots: 2, plus_minus: 0, toi_sec: 1200, hits: 1, blocked_shots: 0, takeaways: 0, giveaways: 0, pim: 0, ...extra })
// 8 games, oldest first: points 0,0,1,1,2,2,3,3
const GAMES = [0, 0, 1, 1, 2, 2, 3, 3].map((p) => game(p))

test('windows shown depend on games played', () => {
  assert.deepEqual(windowsFor(4), [])
  assert.deepEqual(windowsFor(5), [])        // a 5-game window over 5 games is the season
  assert.deepEqual(windowsFor(8), [5])
  assert.deepEqual(windowsFor(12), [5, 10])
  assert.deepEqual(windowsFor(30), [5, 10, 20])
})

test('lastN takes the most recent games, and all of them for null or an oversized window', () => {
  assert.equal(lastN(GAMES, 3).length, 3)
  assert.equal(lastN(GAMES, 3)[0].points, 2)
  assert.equal(lastN(GAMES, null).length, 8)
  assert.equal(lastN(GAMES, 50).length, 8)
})

test('skater form: totals, per-game rates and the recent window', () => {
  const season = skaterForm(GAMES, null)
  assert.equal(season.gp, 8)
  assert.equal(season.points, 12)
  near(season.ppg, 1.5)
  const last5 = skaterForm(GAMES, 5)
  assert.equal(last5.gp, 5)
  assert.equal(last5.points, 1 + 2 + 2 + 3 + 3)
  near(last5.ppg, 11 / 5)
  near(last5.shots, 2)
  near(last5.toi, 1200)
})

test('missing numbers are skipped for averages and counted as zero in totals', () => {
  const rows = [game(1, { shots: null }), game(1, { shots: 4 })]
  near(skaterForm(rows, null).shots, 4)             // averaged over the games that have it
  assert.equal(skaterForm([game(2, { plus_minus: null })], null).plusMinus, 0)
})

test('fantasy points per game come from game rows under your scoring', () => {
  const rows = [game(2, { goals: 1, assists: 1, shots: 4 }), game(0, { goals: 0, assists: 0, shots: 2 })]
  near(skaterForm(rows, null, { goals: 3, assists: 2, shots: 0.5 }).fpg, ((3 + 2 + 2) + (0 + 0 + 1)) / 2)
  near(skaterForm(rows, null, {}).fpg, 0)
})

test('scoring the game log cannot supply is reported', () => {
  assert.deepEqual(missingScoring({ goals: 3, pp_points: 1, game_winning_goals: 2 }), ['pp_points', 'game_winning_goals'])
  assert.deepEqual(missingScoring({ goals: 3, pp_points: 0 }), [])
  assert.deepEqual(missingScoring(undefined), [])
  // and they really are left out of the rate
  near(skaterForm([game(1, { goals: 1, assists: 0 })], null, { goals: 3, pp_points: 5 }).fpg, 3)
})

const goalie = (shots, saves, extra = {}) => ({ shots_against: shots, saves, goals_against: shots - saves, toi_sec: 3600, started: true, decision: 'W', ...extra })

test('goalie form: save %, goals against average and goals saved above average', () => {
  const games = [goalie(30, 27), goalie(20, 20, { decision: 'W' }), goalie(40, 34, { decision: 'L' }), goalie(10, 9, { started: false, toi_sec: 600, decision: null })]
  const s = goalieForm(games, null, 0.9)
  assert.equal(s.gp, 4)
  assert.equal(s.starts, 3)
  assert.equal(s.wins, 2)
  near(s.svPct, 90 / 100)
  near(s.gaa, (10 * 3600) / (3600 * 3 + 600))
  near(s.gsaa, 100 * 0.1 - 10)
  const recent = goalieForm(games, 2, 0.9)
  assert.equal(recent.shots, 50)
  near(recent.svPct, 43 / 50)
})

test('goalie form without a league save % has no GSAA, and an empty window is safe', () => {
  assert.equal(goalieForm([goalie(30, 27)], null, null).gsaa, null)
  const none = goalieForm([], null, 0.9)
  assert.equal(none.gp, 0)
  assert.equal(none.svPct, null)
  assert.equal(none.gaa, null)
})

test('rolling mean is null until a full window, then trails the last w games', () => {
  const r = rollingMean(GAMES, 3, (g) => g.points)
  assert.deepEqual(r.slice(0, 2), [null, null])
  near(r[2], 1 / 3)
  near(r[7], (2 + 3 + 3) / 3)               // the last three games: 2, 3, 3
  assert.equal(r.length, GAMES.length)
})

test('rolling mean ignores games without a value', () => {
  const rows = [{ v: 1 }, { v: null }, { v: 3 }]
  near(rollingMean(rows, 3, (g) => g.v)[2], 2)
  assert.equal(rollingMean([{ v: null }, { v: null }], 2, (g) => g.v)[1], null)
})

test('rolling ratio is a ratio of sums, not a mean of ratios', () => {
  const saves = (g) => g.saves
  const shots = (g) => g.shots_against
  const games = [goalie(10, 10), goalie(40, 32), goalie(30, 24)]   // 1.000, .800, .800 by game
  const r = rollingRatio(games, 2, saves, shots)
  assert.equal(r[0], null)
  near(r[1], 42 / 50)                       // .840 as a ratio of sums; the mean of the two game rates would be .900
  near(r[2], 56 / 70)
  assert.equal(rollingRatio([goalie(0, 0), goalie(0, 0)], 2, saves, shots)[1], null)
})
