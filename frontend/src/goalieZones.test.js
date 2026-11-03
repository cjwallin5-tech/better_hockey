import test from 'node:test'
import assert from 'node:assert/strict'
import { clampLabel, gloveSign, polar, zoneCentre, zonePolygon, zoneStrength } from './goalieZones.js'

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

test('the middle close label sits further out than the two beside it, so the three do not collide', () => {
  const mid = zoneCentre('close', 'middle', 1)
  const side = zoneCentre('close', 'glove', -1)
  assert.ok(89 - mid.x > 89 - side.x + 2)
  assert.ok(Math.hypot(mid.x - side.x, mid.y - side.y) > 5)
})

test('labels are kept inside the edges of the map', () => {
  assert.equal(clampLabel(10, 0, 200), 36)
  assert.equal(clampLabel(195, 0, 200), 164)
  assert.equal(clampLabel(100, 0, 200), 100)
})
