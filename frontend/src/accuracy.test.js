// Run with: npm test   (Node's built-in test runner; no extra packages)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { binLabel, calibrationSentence, miscalibrated, verdictFor } from './accuracy.js'

test('a paired difference is better, worse or unclear by whether its interval excludes zero', () => {
  assert.equal(verdictFor({ mean: -0.01, low: -0.02, high: -0.001 }), 'better')
  assert.equal(verdictFor({ mean: 0.01, low: 0.001, high: 0.02 }), 'worse')
  assert.equal(verdictFor({ mean: -0.002, low: -0.018, high: 0.014 }), 'unclear')
  assert.equal(verdictFor(null), 'unclear')
})

test('bins that disagree with reality by enough over enough games are flagged with a direction', () => {
  const bins = [
    { lo: 0.5, hi: 0.6, n: 59, mean_p: 0.55, rate: 0.53 },
    { lo: 0.8, hi: 0.9, n: 30, mean_p: 0.84, rate: 0.6 },
    { lo: 0.0, hi: 0.4, n: 6, mean_p: 0.38, rate: 0.17 },       // too few to say
    { lo: 0.55, hi: 0.6, n: 25, mean_p: 0.57, rate: 0.85 },
  ]
  const out = miscalibrated(bins)
  assert.deepEqual(out.map((b) => [b.lo, b.direction]), [[0.8, 'over'], [0.55, 'under']])
  assert.deepEqual(miscalibrated(undefined), [])
})

test('sentences and labels', () => {
  assert.equal(calibrationSentence({ mean_p: 0.93, n: 41, rate: 0.78 }, 'the top pick started'), 'When it said about 93% (41 games), the top pick started 78% of the time.')
  assert.equal(binLabel({ lo: 0.4, hi: 0.45 }), '40%-45%')
  assert.equal(binLabel({ lo: 0.6, hi: 1.0 }), '60%+')
})
