// Run with: npm test   (Node's built-in test runner; no extra packages)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { categoryAmounts, streamingBoard, windowPoints, windowTotals } from './streaming.js'

const near = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} is not within ${eps} of ${b}`)
const line = (o = {}) => ({ win: 0.5, loss: 0.39, otl: 0.11, saves: 24, shots: 27, ga: 3, shutout: 0.05, ...o })
const game = (probability, lineOverrides = {}) => ({ probability, line: line(lineOverrides) })
const LEAGUE = { goals_pg: 3.0, shots_pg: 27.0 }

test('window totals weight each game by the chance he starts it', () => {
  const t = windowTotals([game(1.0), game(0.5, { win: 0.7, ga: 2 })])
  near(t.starts, 1.5)
  near(t.win, 0.5 + 0.5 * 0.7)
  near(t.ga, 3 + 0.5 * 2)
  near(t.saves, 24 + 0.5 * 24)
})

test('a goalie with no chance to start adds nothing', () => {
  const t = windowTotals([game(0)])
  assert.equal(t.starts, 0)
  assert.equal(t.win, 0)
  assert.equal(windowTotals([]).starts, 0)
})

test('points under your scoring: wins, saves, goals against, shutouts, losses', () => {
  const t = windowTotals([game(1.0)])
  near(windowPoints(t, { wins: 4, saves: 0.2, goals_against: -1, shutouts: 3 }), 4 * 0.5 + 0.2 * 24 - 3 + 3 * 0.05)
  near(windowPoints(t, { losses: -2, ot_losses: -1 }), -2 * 0.39 - 1 * 0.11)
  near(windowPoints(t, {}), 0)
  near(windowPoints(t, undefined), 0)
})

test('more expected starts means more points when the scoring is positive', () => {
  const scoring = { wins: 4, saves: 0.2 }
  assert.ok(windowPoints(windowTotals([game(1), game(1)]), scoring) > windowPoints(windowTotals([game(1)]), scoring))
})

test('category amounts: counting categories and the sign of lower-is-better ones', () => {
  const t = windowTotals([game(1.0)])
  near(categoryAmounts(t, 'wins', LEAGUE), 0.5)
  near(categoryAmounts(t, 'losses', LEAGUE), -0.39)
  near(categoryAmounts(t, 'goals_against', LEAGUE), -3)
  near(categoryAmounts(t, 'saves', LEAGUE), 24)
  near(categoryAmounts(t, 'shutouts', LEAGUE), 0.05)
  assert.equal(categoryAmounts(t, 'nonsense', LEAGUE), 0)
})

test('GAA is valued against an average goalie over his starts, save % by saves above average on the same shots', () => {
  // an average start: 3 goals against on 27 shots (league 3.0 and 27)
  near(categoryAmounts(windowTotals([game(1.0)]), 'gaa', LEAGUE), 0)
  near(categoryAmounts(windowTotals([game(1.0)]), 'save_pct', LEAGUE), 0)
  // 2 goals against and 25 saves on 27 shots: a better start
  const good = windowTotals([game(1.0, { ga: 2, saves: 25 })])
  near(categoryAmounts(good, 'gaa', LEAGUE), 1)
  near(categoryAmounts(good, 'save_pct', LEAGUE), 25 - (1 - 3 / 27) * 27)
  assert.ok(categoryAmounts(good, 'save_pct', LEAGUE) > 0)
  // a half chance to start halves the effect
  near(categoryAmounts(windowTotals([game(0.5, { ga: 2, saves: 25 })]), 'gaa', LEAGUE), 0.5 * 3 - 0.5 * 2 + 0.5 * 0)
})

const plan = [
  { player_id: 1, name: 'Busy', team: 'AAA', games: [game(1), game(1), game(1)] },
  { player_id: 2, name: 'Backup', team: 'BBB', games: [game(0.2), game(0.2)] },
  { player_id: 3, name: 'Soft schedule', team: 'CCC', games: [game(1, { win: 0.62, ga: 2.4, saves: 23, shots: 25.4 }), game(1, { win: 0.6, ga: 2.5, saves: 23, shots: 25.5 })] },
]

test('points board: ranked by projected fantasy points, best first', () => {
  const board = streamingBoard({ plan, scoring: { wins: 4, saves: 0.2, goals_against: -1 }, categories: null, league: LEAGUE })
  assert.equal(board[0].id, 1)                                   // three starts at 3.8 points beat two better ones at about 4.6
  assert.deepEqual(board.map((r) => r.id).sort(), [1, 2, 3])
  assert.ok(board[0].score >= board[1].score && board[1].score >= board[2].score)
  assert.equal(board[2].id, 2)                                   // the backup with little chance to start is last
  near(board[0].totals.starts, board[0].games.reduce((t, g) => t + g.probability, 0))
})

test('category board: z-scores over the chosen goalie categories only, best first', () => {
  const board = streamingBoard({ plan, scoring: {}, categories: { skater: [], goalie: ['wins', 'saves'] }, league: LEAGUE })
  assert.deepEqual(Object.keys(board[0].z).sort(), ['saves', 'wins'])
  near(board[0].score, board[0].z.wins + board[0].z.saves)
  assert.ok(board[0].score >= board[2].score)
  assert.equal(board[2].id, 2)
})

test('a category league with no goalie categories scores everyone zero', () => {
  const board = streamingBoard({ plan, scoring: {}, categories: { skater: [], goalie: [] }, league: LEAGUE })
  assert.ok(board.every((r) => r.score === 0))
})

test('an empty plan is an empty board', () => {
  assert.deepEqual(streamingBoard({ plan: [], scoring: {}, categories: null, league: LEAGUE }), [])
})
