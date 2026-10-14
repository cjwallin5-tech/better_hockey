// Run with: npm test   (Node's built-in test runner; no extra packages)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { clock, corsiModel, gameEnd, mmss, xgModel } from './gameFlow.js'

const shot = (period, time_sec, team, xg, situation = '1551') => ({ period, time_sec, team, xg, situation })
const SHOTS = [
  shot(1, 100, 'AAA', 0.1),
  shot(1, 200, 'BBB', 0.3),
  shot(1, 300, 'AAA', 0.2, '1451'),   // power play
  shot(2, 1500, 'AAA', 0.5),
  shot(5, 3601, 'BBB', 0.9),          // shootout: never plotted
]
const GOALS = [
  { period: 1, time_sec: 100, team: 'AAA', scorer: 'Ann Scorer', xg: 0.1 },
  { period: 5, time_sec: 3601, team: 'BBB', scorer: 'Shootout Sam' },
]
const base = { shots: SHOTS, goals: GOALS, away: 'AAA', home: 'BBB' }
const last = (line) => line.pts[line.pts.length - 1][1]

test('clock labels periods and overtime', () => {
  assert.equal(clock(1), 'P1 0:01')
  assert.equal(clock(1200), 'P1 20:00')
  assert.equal(clock(1201), 'P2 0:01')
  assert.equal(clock(3601), 'OT 0:01')
  assert.equal(mmss(75), '1:15')
})

test('the time axis is 60 minutes, or ends with a short overtime', () => {
  assert.equal(gameEnd([{ time_sec: 3000 }]), 3600)
  assert.equal(gameEnd([{ time_sec: 3679 }]), 3720)
})

test('xG flow adds up each team\'s expected goals and ignores shootout attempts', () => {
  const m = xgModel(base)
  assert.equal(m.lines[0].total.toFixed(2), '0.80')
  assert.equal(m.lines[1].total.toFixed(2), '0.30')
  assert.deepEqual(m.lines.map((l) => l.endLabel), ['AAA 0.80', 'BBB 0.30'])
  assert.equal(m.dots.length, 1)                       // the shootout goal is not drawn
  assert.equal(m.dots[0].v.toFixed(2), '0.10')         // the dot sits on the line after the goal's own xG
  assert.match(m.dots[0].tip, /AAA goal · Ann Scorer · P1 1:40 · 10% xG/)
  assert.ok(m.domain.max >= 0.8)
})

test('attempts view counts every attempt, or only 5v5 ones', () => {
  const all = corsiModel({ ...base, view: 'attempts', strength: 'all' })
  assert.deepEqual(all.lines.map(last), [3, 1])
  const five = corsiModel({ ...base, view: 'attempts', strength: '5v5' })
  assert.deepEqual(five.lines.map(last), [2, 1])
  assert.equal(all.dots.length, 1)
  assert.equal(all.dots[0].v, 1)                       // one AAA attempt by the time of the goal
})

test('difference view is away attempts minus home attempts, over time', () => {
  const all = corsiModel({ ...base, view: 'difference', strength: 'all' })
  assert.equal(last(all.lines[0]), 2)                  // 3 - 1
  assert.equal(all.lines[0].endLabel, '+2 AAA')
  const five = corsiModel({ ...base, view: 'difference', strength: '5v5' })
  assert.equal(last(five.lines[0]), 1)                 // 2 - 1
  // the line steps by one at each attempt, in time order
  const path = all.lines[0].pts.map(([, v]) => v)
  assert.deepEqual(path.slice(0, 5), [0, 0, 1, 1, 0])
})

test('the home team leading shows as a negative difference', () => {
  const m = corsiModel({ shots: [shot(1, 10, 'BBB', 0.1), shot(1, 20, 'BBB', 0.1)], goals: [], away: 'AAA', home: 'BBB', view: 'difference', strength: 'all' })
  assert.equal(last(m.lines[0]), -2)
  assert.equal(m.lines[0].endLabel, '-2 BBB')
  assert.ok(m.domain.min <= -2)
})

test('every plotted point stays inside the axis, in every view', () => {
  for (const view of ['attempts', 'difference']) {
    for (const strength of ['all', '5v5']) {
      const m = corsiModel({ ...base, view, strength })
      const values = m.lines.flatMap((l) => l.pts.map((p) => p[1]))
      assert.ok(values.every((v) => v >= m.domain.min && v <= m.domain.max), `${view}/${strength}`)
      assert.ok(m.domain.ticks.includes(0), `${view}/${strength} has a zero tick`)
    }
  }
})

test('a game with no shots still draws flat lines', () => {
  const m = corsiModel({ shots: [], goals: [], away: 'AAA', home: 'BBB', view: 'attempts', strength: 'all' })
  assert.deepEqual(m.lines.map(last), [0, 0])
  assert.equal(m.dots.length, 0)
})
