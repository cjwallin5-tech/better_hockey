import test from 'node:test'
import assert from 'node:assert/strict'
import { gloveSign, polar, zoneCentre, zonePolygon, zoneStrength } from './goalieZones.js'

test('glove side is toward negative y for a left-catching goalie', () => {
  assert.equal(gloveSign('L'), -1)
  assert.equal(gloveSign('R'), 1)
  assert.equal(gloveSign(null), -1)
})

test('polar points sit at the right distance and out in front of the net', () => {
  const p = polar(20, 0, 1)
  assert.ok(Math.abs(p.x - 69) < 1e-9 && Math.abs(p.y) < 1e-9)
  const q = polar(20, 90, -1)
  assert.ok(Math.abs(q.x - 89) < 1e-9 && Math.abs(q.y + 20) < 1e-9)
})

test('every zone polygon stays within its range and on its side', () => {
  for (const range of ['close', 'mid', 'long']) {
    for (const [lane, sign] of [['glove', -1], ['blocker', 1], ['middle', 1]]) {
      const pts = zonePolygon(range, lane, sign)
      assert.ok(pts.length >= 10)
      for (const p of pts) {
        assert.ok(Math.hypot(89 - p.x, p.y) <= 62 + 1e-9)
        if (lane !== 'middle') assert.ok(p.y * sign >= -1e-9, `${range} ${lane} point on the wrong side`)
      }
    }
  }
})

test('the middle lane is narrow and the side lanes are not', () => {
  const widest = (pts) => Math.max(...pts.map((p) => Math.abs(p.y)))
  assert.ok(widest(zonePolygon('mid', 'middle', 1)) < 10)
  assert.ok(widest(zonePolygon('mid', 'glove', -1)) > 30)
})

test('labels sit inside the zone and strength saturates at two standard deviations', () => {
  const c = zoneCentre('mid', 'glove', -1)
  assert.ok(c.y < 0)
  assert.equal(zoneStrength(-3), 1)
  assert.equal(zoneStrength(1), 0.5)
  assert.equal(zoneStrength(null), 0)
})
