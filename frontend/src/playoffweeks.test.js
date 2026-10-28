// Run with: npm test   (Node's built-in test runner; no extra packages)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { backToBacks, buildWeeks, defaultRange, goaliesInRange, mondayOf, planWeeks, playerWeeks, rangeFromSaved, rosterWeek, teamWindows, weekIndex } from './playoffweeks.js'

test('weeks run Monday to Sunday and cover every date', () => {
  assert.equal(mondayOf('2026-10-27'), '2026-10-26')   // a Tuesday
  assert.equal(mondayOf('2026-11-01'), '2026-10-26')   // the Sunday after it
  assert.equal(mondayOf('2026-11-02'), '2026-11-02')
  const weeks = buildWeeks(['2026-10-27', '2026-11-08', '2026-11-03'])
  assert.deepEqual(weeks, [{ start: '2026-10-26', end: '2026-11-01' }, { start: '2026-11-02', end: '2026-11-08' }])
  assert.equal(weekIndex('2026-11-08', weeks), 1)
  assert.equal(weekIndex('2026-12-01', weeks), -1)
  assert.deepEqual(buildWeeks([]), [])
})

test('the default window is the last three weeks, and a saved one is kept only while it still fits', () => {
  const weeks = buildWeeks(['2027-03-01', '2027-04-11'])    // 6 weeks
  assert.deepEqual(defaultRange(weeks), { from: 3, to: 5 })
  assert.deepEqual(defaultRange(buildWeeks(['2027-04-05']), 3), { from: 0, to: 0 })
  assert.deepEqual(rangeFromSaved({ from: weeks[1].start, to: weeks[2].start }, weeks), { from: 1, to: 2 })
  assert.deepEqual(rangeFromSaved({ from: weeks[2].start, to: weeks[1].start }, weeks), defaultRange(weeks))   // backwards
  assert.deepEqual(rangeFromSaved({ from: '1999-01-04', to: '1999-01-11' }, weeks), defaultRange(weeks))
  assert.deepEqual(rangeFromSaved(null, weeks), defaultRange(weeks))
})

test('back-to-backs count games the day after another', () => {
  assert.equal(backToBacks(['2027-03-01', '2027-03-02', '2027-03-04']), 1)
  assert.equal(backToBacks(['2027-03-01', '2027-03-02', '2027-03-03']), 2)
  assert.equal(backToBacks(['2027-03-01', '2027-03-03']), 0)
  assert.equal(backToBacks([]), 0)
})

const g = (date, skater_ratio, goalie_ratio = 1) => ({ date, skater_ratio, goalie_ratio, opponent: 'X', home_game: true })
const teams = [
  { team: 'AAA', name: 'A', games: [g('2027-03-01', 1.2), g('2027-03-02', 1.1), g('2027-03-08', 1.0), g('2027-03-20', 0.5)] },
  { team: 'BBB', name: 'B', games: [g('2027-03-03', 0.8)] },
]
const weeks = buildWeeks(['2027-03-01', '2027-03-21'])   // Mar 1-7, 8-14, 15-21

test('team windows count games per week, back-to-backs and how soft the games are, only inside the window', () => {
  const rows = teamWindows(teams, weeks, { from: 0, to: 1 })
  const a = rows.find((r) => r.team === 'AAA')
  assert.deepEqual(a.weeks, [2, 1])
  assert.equal(a.games, 3)                    // the Mar 20 game is outside
  assert.equal(a.backToBacks, 1)
  assert.ok(Math.abs(a.skaters - 1.1) < 1e-9)
  assert.ok(Math.abs(a.index - 0.3) < 1e-9)
  const b = rows.find((r) => r.team === 'BBB')
  assert.deepEqual(b.weeks, [1, 0])
  assert.ok(b.index < 0)
})

test('a team with no games in the window has no average and no index', () => {
  const rows = teamWindows([{ team: 'CCC', name: 'C', games: [] }], weeks, { from: 0, to: 2 })
  assert.deepEqual(rows[0].weeks, [0, 0, 0])
  assert.equal(rows[0].skaters, null)
  assert.equal(rows[0].index, 0)
})

test('a roster follows its teams across the dates asked for', () => {
  const week = rosterWeek({ roster: [{ id: 1, kind: 'skater' }, { id: 2, kind: 'skater' }, { id: 3, kind: 'skater' }], teams, teamOf: (id) => ({ 1: 'AAA', 2: 'BBB' })[id], first: '2027-03-01', last: '2027-03-07', gamesOut: (id) => (id === 2 ? 4 : 0) })
  assert.deepEqual(week[1].games.map((x) => x.game_date), ['2027-03-01', '2027-03-02'])
  assert.deepEqual(week[2].games.map((x) => x.game_date), ['2027-03-03'])
  assert.deepEqual(week[3].games, [])           // no team known
  assert.equal(week[2].games_out, 4)
})

test('goalie plans are cut to the dates asked for', () => {
  const out = goaliesInRange([{ player_id: 9, games: [{ date: '2027-03-01' }, { date: '2027-03-09' }] }], '2027-03-01', '2027-03-07')
  assert.deepEqual(out[0].games.map((x) => x.date), ['2027-03-01'])
  assert.deepEqual(goaliesInRange(null, 'a', 'b'), [])
})

const entry = (id, group, scores) => ({ id, name: `P${id}`, kind: 'skater', group, known: true, out: 0, games: Object.entries(scores).map(([date, score]) => ({ date, score })) })

test('each week is worth the best lineup it can field, and the unused games are counted but not scored', () => {
  const entries = [entry(1, 'C', { '2027-03-01': 3, '2027-03-02': 3, '2027-03-09': 3 }), entry(2, 'C', { '2027-03-01': 2, '2027-03-10': 2 })]
  const out = planWeeks({ entries, slots: { C: 1 }, weeks, range: { from: 0, to: 1 } })
  assert.deepEqual(out.weeks.map((w) => [w.games, w.starts, w.score]), [[3, 2, 6], [2, 2, 5]])
  assert.equal(out.total, 11)
  const rows = playerWeeks({ entries, plan: out.plan, weeks, range: { from: 0, to: 1 } })
  assert.deepEqual(rows[0].weeks, [2, 1])
  assert.equal(rows[0].total, 3)
  assert.equal(rows[1].starts, 1)
})

test('games outside the chosen weeks are ignored', () => {
  const entries = [entry(1, 'C', { '2027-03-01': 3, '2027-03-16': 9 })]
  const out = planWeeks({ entries, slots: { C: 1 }, weeks, range: { from: 0, to: 0 } })
  assert.equal(out.weeks[0].games, 1)
})
