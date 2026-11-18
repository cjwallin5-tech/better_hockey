import test from 'node:test'
import assert from 'node:assert/strict'
import { goaliePeers, goaliePercentiles, percentileAmong } from './goaliePercentiles.js'

test('percentile is the share of peers the value is at least as good as, flipped when lower is better', () => {
  assert.equal(percentileAmong(3, [1, 2, 3, 4], true), 75)
  assert.equal(percentileAmong(2, [1, 2, 3, 4], false), 75)
  assert.equal(percentileAmong(null, [1, 2], true), null)
  assert.equal(percentileAmong(1, [null], true), null)
})

test('peers are goalies with at least half the starts of the busiest', () => {
  const gs = [{ games_started: 20 }, { games_started: 10 }, { games_started: 9 }, { games_started: 0 }]
  const { peers, minStarts } = goaliePeers(gs)
  assert.equal(minStarts, 10)
  assert.equal(peers.length, 2)
})

test('a goalie is ranked among the peers on each card', () => {
  const gs = [
    { games_started: 10, save_pct: 0.91, gaa: 2.5, gsaa: 3, gsaa_per60: 0.1, quality_start_pct: 0.6, shutouts: 1 },
    { games_started: 10, save_pct: 0.92, gaa: 2.2, gsaa: 6, gsaa_per60: 0.2, quality_start_pct: 0.7, shutouts: 2 },
    { games_started: 2, save_pct: 0.5, gaa: 9, gsaa: -9, gsaa_per60: -1, quality_start_pct: 0, shutouts: 0 },
  ]
  const { percentiles, peerCount } = goaliePercentiles(gs[1], gs)
  assert.equal(peerCount, 2)
  assert.equal(percentiles.save_pct, 100)
  assert.equal(percentiles.gaa, 100)
  assert.equal(goaliePercentiles(gs[0], gs).percentiles.gaa, 50)
})
