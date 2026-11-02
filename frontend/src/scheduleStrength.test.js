import test from 'node:test'
import assert from 'node:assert/strict'
import { biggestSwing, difficultyRanks, extreme, fmtNet, fmtPts } from './scheduleStrength.js'

test('points and margins carry a sign', () => {
  assert.equal(fmtPts(0.64), '+0.6')
  assert.equal(fmtPts(-0.8), '-0.8')
  assert.equal(fmtPts(null), '–')
  assert.equal(fmtNet(0.09), '+0.09')
})

test('the lowest expected points is the hardest schedule', () => {
  const rows = [{ team: 'A', v: 0.5 }, { team: 'B', v: -0.7 }, { team: 'C', v: null }, { team: 'D', v: 0.1 }]
  assert.deepEqual(difficultyRanks(rows, (r) => r.v), { B: 1, D: 2, A: 3 })
})

test('only the ends are labelled', () => {
  assert.equal(extreme(1, 32), 'hardest')
  assert.equal(extreme(5, 32), 'hardest')
  assert.equal(extreme(6, 32), '')
  assert.equal(extreme(28, 32), 'easiest')
  assert.equal(extreme(27, 32), '')
  assert.equal(extreme(null, 32), '')
})

test('the biggest swing ignores sign and missing values', () => {
  assert.equal(biggestSwing([{ v: -0.8 }, { v: 0.6 }, { v: null }], (r) => r.v), 0.8)
  assert.equal(biggestSwing([], (r) => r.v), 0)
})
