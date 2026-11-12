import test from 'node:test'
import assert from 'node:assert/strict'
import { defaultMonth, monthShort, monthTitle, monthsOf, monthWeeks, recordOf, recordText, resultText, todayIso } from './calendar.js'

const g = (date, result, us, them, period) => ({ date, result, us, them, period })

test('monthsOf lists each month once, earliest first', () => {
  assert.deepEqual(monthsOf([g('2026-11-02'), g('2026-09-29'), g('2026-11-20'), g('2027-01-05')]), ['2026-09', '2026-11', '2027-01'])
  assert.deepEqual(monthsOf([]), [])
})

test('month names', () => {
  assert.equal(monthTitle('2026-10'), 'October 2026')
  assert.equal(monthTitle('2027-01'), 'January 2027')
  assert.equal(monthShort('2026-12'), 'Dec')
})

test('a month is laid out in Sunday-first weeks, padded with empty cells', () => {
  // October 2026 starts on a Thursday and has 31 days: 4 empty cells, 31 days, then 0 padding is not needed (4+31=35)
  const weeks = monthWeeks('2026-10', new Map())
  assert.equal(weeks.length, 5)
  assert.ok(weeks.every((w) => w.length === 7))
  assert.deepEqual(weeks[0].map((c) => c && c.day), [null, null, null, null, 1, 2, 3])
  assert.equal(weeks[4][6].day, 31)
})

test('a month that spills into a sixth week and pads the end', () => {
  // August 2026 starts on a Saturday: 6 empty cells, 31 days = 37 cells -> 6 weeks
  const weeks = monthWeeks('2026-08', new Map())
  assert.equal(weeks.length, 6)
  assert.equal(weeks[0][6].day, 1)
  assert.deepEqual(weeks[5].map((c) => c && c.day), [30, 31, null, null, null, null, null])
})

test('February in a leap year has 29 days', () => {
  const days = monthWeeks('2028-02', new Map()).flat().filter(Boolean)
  assert.equal(days.length, 29)
})

test('a game is attached to its date', () => {
  const game = { date: '2026-10-14', game_id: 5 }
  const cell = monthWeeks('2026-10', new Map([['2026-10-14', game]])).flat().find((c) => c && c.day === 14)
  assert.equal(cell.game, game)
  assert.equal(cell.date, '2026-10-14')
})

test('record counts finished games only', () => {
  const r = recordOf([g('a', 'W'), g('b', 'W'), g('c', 'L'), g('d', 'OTL'), g('e', null)])
  assert.deepEqual(r, { w: 2, l: 1, otl: 1 })
  assert.equal(recordText(r), '2-1-1')
  assert.equal(recordText(recordOf([g('a', null)])), '')
})

test('result text includes the overtime or shootout marker', () => {
  assert.equal(resultText(g('a', 'W', 4, 2, null)), 'W 4-2')
  assert.equal(resultText(g('a', 'OTL', 2, 3, 'OT')), 'OTL 2-3 OT')
  assert.equal(resultText(g('a', 'W', 3, 2, 'SO')), 'W 3-2 SO')
})

test('todayIso is the local calendar date', () => {
  assert.equal(todayIso(new Date(2026, 10, 9, 23, 59)), '2026-11-09')
  assert.equal(todayIso(new Date(2027, 0, 5, 0, 1)), '2027-01-05')
})

test('the calendar opens on the current month, or the nearest end of the season', () => {
  const months = ['2026-09', '2026-10', '2026-11', '2027-04']
  assert.equal(defaultMonth(months, '2026-11-10'), '2026-11')
  assert.equal(defaultMonth(months, '2026-08-01'), '2026-09')   // before the season
  assert.equal(defaultMonth(months, '2027-06-20'), '2027-04')   // after it
  assert.equal(defaultMonth(months, '2027-02-14'), '2027-04')   // a gap in the schedule: later than the first month, so the last
  assert.equal(defaultMonth([], '2026-11-10'), null)
})
