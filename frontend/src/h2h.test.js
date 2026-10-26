// Run with: npm test   (Node's built-in test runner; no extra packages)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { gameVariance, matchNames, normalCdf, pointScale, teamWeek, winChance } from './h2h.js'

const entry = (id, group, games, kind = group === 'G' ? 'goalie' : 'skater') => ({ id, name: `P${id}`, kind, group, games })
const near = (a, b, eps = 1e-6) => assert.ok(Math.abs(a - b) < eps, `${a} vs ${b}`)

test('normal CDF matches known values', () => {
  near(normalCdf(0), 0.5)
  near(normalCdf(1), 0.8413447, 1e-6)
  near(normalCdf(-1.96), 0.0249979, 1e-5)
  near(normalCdf(3), 0.9986501, 1e-6)
})

test('point scale is the average weight of a goal or assist, 1 when neither counts', () => {
  assert.equal(pointScale({ goals: 3, assists: 2 }), 2.5)
  assert.equal(pointScale({ goals: 1, assists: 1 }), 1)
  assert.equal(pointScale({ goals: 3 }), 3)
  assert.equal(pointScale({ wins: 4 }), 1)
})

test('skater variance grows with the expected score; a goalie who may not start swings more than a sure one', () => {
  const sk = entry(1, 'C', [])
  assert.ok(gameVariance(sk, { score: 2 }, 1) > gameVariance(sk, { score: 1 }, 1))
  const g = entry(2, 'G', [])
  const sure = gameVariance(g, { score: 8, chance: 1 }, 1)
  const maybe = gameVariance(g, { score: 8, chance: 0.5 }, 1) // a start is worth 16 half the time
  assert.ok(maybe > sure)
  assert.equal(gameVariance(g, { score: 0, chance: 0 }, 1), 0)
})

test('a team week adds the started games and lists who started', () => {
  const entries = [entry(1, 'C', [{ date: '2026-10-27', score: 3 }, { date: '2026-10-28', score: 3 }]), entry(2, 'C', [{ date: '2026-10-27', score: 2 }])]
  const w = teamWeek({ entries, slots: { C: 1 }, mode: 'daily', scoring: {} })
  assert.equal(w.total, 6)
  assert.deepEqual(w.days, [{ date: '2026-10-27', total: 3 }, { date: '2026-10-28', total: 3 }])
  assert.deepEqual(w.starters.map((s) => s.id), [1])
  assert.ok(w.variance > 0)
})

test('days can be padded so both teams share a calendar', () => {
  const w = teamWeek({ entries: [entry(1, 'C', [{ date: '2026-10-27', score: 3 }])], slots: { C: 1 }, mode: 'daily', scoring: {}, dates: ['2026-10-27', '2026-10-28'] })
  assert.deepEqual(w.days.map((d) => d.total), [3, 0])
})

test('win chance: even teams are 50%, the bigger total is favored, no swing means the bigger total wins', () => {
  near(winChance({ total: 50, variance: 20 }, { total: 50, variance: 20 }), 0.5)
  assert.ok(winChance({ total: 60, variance: 20 }, { total: 50, variance: 20 }) > 0.9)
  assert.ok(winChance({ total: 52, variance: 400 }, { total: 50, variance: 400 }) < 0.6)
  assert.equal(winChance({ total: 5, variance: 0 }, { total: 4, variance: 0 }), 1)
  near(winChance({ total: 10, variance: 5 }, { total: 8, variance: 5 }) + winChance({ total: 8, variance: 5 }, { total: 10, variance: 5 }), 1)
})

const data = {
  skaters: [{ player_id: 1, name: 'Connor McDavid', games_played: 10 }, { player_id: 2, name: 'Alex Petrović', games_played: 8 }, { player_id: 5, name: 'Sam Smith', games_played: 2 }, { player_id: 6, name: 'Sam Smith', games_played: 9 }],
  goalies: [{ player_id: 3, name: 'Jake Oettinger', games_played: 9 }],
}

test('paste: one name per line, ignoring numbering, team and accents', () => {
  const { matched, unmatched } = matchNames('1. Connor McDavid (EDM)\nalex petrovic - D\nJake Oettinger\nNobody Real\n', data)
  assert.deepEqual(matched.map((m) => [m.id, m.kind]), [[1, 'skater'], [2, 'skater'], [3, 'goalie']])
  assert.deepEqual(unmatched, ['Nobody Real'])
})

test('paste: comma-separated on one line, duplicates once, shared names go to the player with more games', () => {
  const { matched, unmatched } = matchNames('Connor McDavid, Sam Smith, connor mcdavid', data)
  assert.deepEqual(matched.map((m) => m.id), [1, 6])
  assert.deepEqual(unmatched, [])
})
