// Run with: npm test   (Node's built-in test runner; no extra packages)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { baseRate, buildEntries, goalieGameScore, optimize, skaterGameScore } from './lineup.js'

const entry = (id, group, scores) => ({ id, name: `P${id}`, kind: group === 'G' ? 'goalie' : 'skater', group, games: Object.entries(scores).map(([date, score]) => ({ date, score })) })
const ids = (set) => [...set].sort((a, b) => a - b)

test('a soft matchup raises a score and a tough one lowers it, also for a negative rate', () => {
  assert.ok(skaterGameScore(2, 1.1) > 2)
  assert.ok(skaterGameScore(2, 0.9) < 2)
  assert.ok(skaterGameScore(-1, 1.1) > -1)
  assert.equal(skaterGameScore(2, null), 2)
})

test('daily: each day fills the slots from the players who play that day', () => {
  const entries = [entry(1, 'C', { '2026-10-27': 3, '2026-10-28': 3 }), entry(2, 'C', { '2026-10-27': 2 }), entry(3, 'C', { '2026-10-28': 1 })]
  const out = optimize({ entries, slots: { C: 1 } })
  assert.deepEqual(ids(out.starts.get('2026-10-27')), [1])
  assert.deepEqual(ids(out.starts.get('2026-10-28')), [1])
  assert.equal(out.total, 6)
  assert.deepEqual(out.byPlayer.get(2), { starts: 0, score: 0, sat: 1, satScore: 2 })
})

test('daily: a bench player starts on the night the better player has no game', () => {
  const entries = [entry(1, 'C', { '2026-10-27': 5 }), entry(2, 'C', { '2026-10-27': 4, '2026-10-28': 4 })]
  const out = optimize({ entries, slots: { C: 1 } })
  assert.deepEqual(ids(out.starts.get('2026-10-28')), [2])
  assert.equal(out.total, 9)
})

test('weekly: the same players start all week, chosen by week total', () => {
  const entries = [entry(1, 'C', { '2026-10-27': 5 }), entry(2, 'C', { '2026-10-27': 4, '2026-10-28': 4 })]
  const out = optimize({ entries, slots: { C: 1 }, mode: 'weekly' })
  assert.deepEqual(ids(out.starts.get('2026-10-27')), [2])
  assert.equal(out.total, 8)
  assert.equal(out.byPlayer.get(1).sat, 1)
})

test('groups are filled separately and a group with no slots starts nobody', () => {
  const entries = [entry(1, 'C', { '2026-10-27': 3 }), entry(2, 'D', { '2026-10-27': 1 }), entry(3, 'G', { '2026-10-27': 2 })]
  const out = optimize({ entries, slots: { C: 1, D: 0, G: 1 } })
  assert.deepEqual(ids(out.starts.get('2026-10-27')), [1, 3])
})

test('goalie score is the chance to start times the start worth (points) or the per-start z (categories)', () => {
  const game = { probability: 0.5, line: { win: 0.5, loss: 0.4, otl: 0.1, saves: 25, shots: 28, ga: 3, shutout: 0.1 } }
  assert.ok(Math.abs(goalieGameScore(game, null, { wins: 4, saves: 0.2 }, false) - 0.5 * (4 * 0.5 + 0.2 * 25)) < 1e-9)
  assert.equal(goalieGameScore(game, { zsum: 2, expectedGames: 4 }, {}, true), 0.25)
})

test('baseRate: points use the shrunk rate, categories use z per expected game, unknown players 0', () => {
  assert.equal(baseRate({ shrunk: 1.5 }, false), 1.5)
  assert.equal(baseRate({ zsum: 3, expectedGames: 6 }, true), 0.5)
  assert.equal(baseRate({ zsum: 3, expectedGames: 0 }, true), 0)
  assert.equal(baseRate(undefined, false), 0)
})

test('buildEntries joins the week schedule and the goalie plan to the roster', () => {
  const values = new Map([[1, { group: 'L', shrunk: 2 }], [2, { group: 'G', shrunk: 3 }]])
  const week = { 1: { games: [{ game_date: '2026-10-27', skater_ratio: 1.1, opponent: 'BOS', home_game: true }], games_out: 0 } }
  const streaming = [{ player_id: 2, games: [{ date: '2026-10-27', probability: 1, line: { win: 0.5, loss: 0.5, otl: 0, saves: 20, shots: 22, ga: 2, shutout: 0.1 }, opponent: 'NYR' }] }]
  const roster = [{ id: 1, name: 'A', kind: 'skater' }, { id: 2, name: 'B', kind: 'goalie' }, { id: 3, name: 'C', kind: 'skater' }]
  const out = buildEntries({ roster, week, streaming, values, scoring: { wins: 4 }, isCats: false })
  assert.equal(out[0].group, 'L')
  assert.ok(Math.abs(out[0].games[0].score - 2.2) < 1e-9)
  assert.equal(out[1].games[0].score, 2)
  assert.deepEqual(out[2].games, [])
  assert.equal(out[2].known, false)
})
