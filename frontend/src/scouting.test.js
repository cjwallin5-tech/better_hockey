import test from 'node:test'
import assert from 'node:assert/strict'
import { axisValue, ordinal, radarPoint, radarPolygon, spokeAngle } from './scouting.js'

test('spoke 0 points straight up and the spokes run clockwise', () => {
  assert.equal(spokeAngle(0, 4), -Math.PI / 2)
  const top = radarPoint(0, 4, 100, 100, 100, 50)
  assert.ok(Math.abs(top.x - 100) < 1e-9 && Math.abs(top.y - 50) < 1e-9)
  const right = radarPoint(1, 4, 100, 100, 100, 50)
  assert.ok(Math.abs(right.x - 150) < 1e-9 && Math.abs(right.y - 100) < 1e-9)
})

test('percentiles are clamped and a missing one sits at the centre', () => {
  assert.deepEqual(radarPoint(0, 4, null, 10, 10, 50), { x: 10, y: 10 })
  const over = radarPoint(0, 4, 150, 100, 100, 50)
  assert.ok(Math.abs(over.y - 50) < 1e-9)
  assert.equal(radarPolygon([100, 50, 0, null], 100, 100, 50).split(' ').length, 4)
})

test('ordinals handle the teens', () => {
  assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21, 62, 100].map(ordinal), ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '62nd', '100th'])
  assert.equal(ordinal(null), '–')
})

test('axis values are formatted by kind', () => {
  assert.equal(axisValue({ key: 'icetime', value: 1432.8 }), '23:53')
  assert.equal(axisValue({ key: 'possession', value: 0.607 }), '60.7%')
  assert.equal(axisValue({ key: 'speed', value: 24.013 }), '24.0')
  assert.equal(axisValue({ key: 'scoring', value: 7.119 }), '7.12')
  assert.equal(axisValue({ key: 'scoring', value: null }), '–')
})
