import test from 'node:test'
import assert from 'node:assert/strict'
import { adjustment, clutchVerdict, pct1, signed, signedPts } from './scoreState.js'

test('shares and gaps are formatted for display', () => {
  assert.equal(pct1(0.5234), '52.3%')
  assert.equal(pct1(null), '–')
  assert.equal(signedPts(0.0123), '+1.2')
  assert.equal(signedPts(-0.004), '-0.4')
  assert.equal(signed(2.34), '+2.3')
})

test('only gaps of two standard deviations are called out', () => {
  assert.match(clutchVerdict(1.9), /Within chance/)
  assert.match(clutchVerdict(-1.5), /Within chance/)
  assert.match(clutchVerdict(2.3), /more in close/)
  assert.match(clutchVerdict(-2.3), /less in close/)
  assert.match(clutchVerdict(null), /Too few/)
})

test('the adjustment is adjusted minus raw', () => {
  assert.ok(Math.abs(adjustment({ xg_pct: 0.55, xg_pct_adj: 0.57 }) - 0.02) < 1e-9)
  assert.equal(adjustment({ xg_pct: null, xg_pct_adj: 0.5 }), null)
})
