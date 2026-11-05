import test from 'node:test'
import assert from 'node:assert/strict'
import { nhleText, nhleTitle, nhleSentence, factorPct } from './nhle.js'

const n = { points: 37.6, low: 31.2, high: 44.4, factor: 0.3, pairs: 62 }

test('the figure is the points rounded, a dash without one', () => {
  assert.equal(nhleText(n), '38')
  assert.equal(nhleText(null), '–')
  assert.equal(nhleText({ ...n, points: 0 }), '0')
})

test('the tooltip gives the range, factor and sample, or says why there is none', () => {
  assert.match(nhleTitle(n), /About 38 points over 84 NHL games at that rate.*range 31 to 44.*Factor 0\.30 from 62 players/)
  assert.match(nhleTitle(null), /No NHLe/)
})

test('the sentence names the league and hedges with if he gets there', () => {
  assert.equal(nhleSentence(n, 'OHL'), "At this season's OHL rate he would score about 38 points over 84 NHL games (range 31 to 44), if he gets there.")
  assert.equal(nhleSentence(null, 'OHL'), null)
})

test('an earlier season and an age adjustment are said in the tooltip and the sentence', () => {
  const old = { ...n, earlier: true, season_id: 20252026, age_mult: 1.1 }
  assert.match(nhleTitle(old), /^Based on his 2025-26 season, since this one is under 20 games\./)
  assert.match(nhleTitle(old), /Adjusted by 1\.10 for his age\./)
  assert.doesNotMatch(nhleTitle({ ...n, age_mult: 1 }), /Adjusted/)
  assert.match(nhleSentence(old, 'OHL'), /^At his 2025-26 rate he would score about 38 points/)
})

test('a factor reads as a percent', () => {
  assert.equal(factorPct(0.306), '31%')
})
