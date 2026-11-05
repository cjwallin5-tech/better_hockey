import test from 'node:test'
import assert from 'node:assert/strict'
import { goalieProjectionNote, goalieProjectionFigures, goalieRange, fmtSavePct, fmtGaa } from './goalieProjection.js'

const row = { wins: 10, rest_starts: 53.8, rest_wins: 29.4, final_saves: 1613.6, final_goals_against: 181.7, final_shutouts: 3.26,
  final_save_pct: 0.9087, final_gaa: 2.451, low_wins: 33.6, high_wins: 44.2, low_shutouts: 1.26, high_shutouts: 5.8 }

test('the note says what he has plus what is still expected', () => {
  assert.equal(goalieProjectionNote(row), '10 wins so far, plus about 29 over the 54 starts still to come.')
})

test('singular wording for one win and one start', () => {
  assert.match(goalieProjectionNote({ ...row, wins: 1, rest_starts: 1.2, rest_wins: 0.6 }), /^1 win so far, plus about 1 over the 1 start still to come\.$/)
})

test('no starts left says so instead of promising more', () => {
  assert.match(goalieProjectionNote({ ...row, rest_starts: 0.2 }), /No more starts are expected/)
})

test('figures are rounded, shutouts keep a decimal, rates read like hockey', () => {
  assert.deepEqual(goalieProjectionFigures(row), [
    { label: 'saves', value: 1614 }, { label: 'save %', value: '.909' }, { label: 'goals against', value: 182 },
    { label: 'GAA', value: '2.45' }, { label: 'shutouts', value: '3.3' }, { label: 'starts left', value: 54 },
  ])
})

test('save % and GAA fall back to a dash', () => {
  assert.equal(fmtSavePct(null), '–')
  assert.equal(fmtGaa(undefined), '–')
  assert.equal(fmtSavePct(0.9), '.900')
})

test('ranges are rounded, shutouts keep a decimal, a missing range is a dash', () => {
  assert.equal(goalieRange(row), '34–44')
  assert.equal(goalieRange(row, 'shutouts'), '1.3–5.8')
  assert.equal(goalieRange({}, 'wins'), '–')
})
