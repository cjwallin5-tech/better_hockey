import test from 'node:test'
import assert from 'node:assert/strict'
import { infoPosition } from './infoPosition.js'

const vp = { width: 1200, height: 800 }

test('opens below the button when there is room', () => {
  assert.deepEqual(infoPosition({ left: 300, top: 100, bottom: 120 }, vp), { top: 126, left: 292 })
})

test('opens above a button near the bottom of the screen', () => {
  assert.deepEqual(infoPosition({ left: 300, top: 700, bottom: 720 }, vp), { bottom: 106, left: 292 })
})

test('stays inside the screen sideways', () => {
  assert.equal(infoPosition({ left: 1190, top: 100, bottom: 120 }, vp).left, 1200 - 320 - 8)
  assert.equal(infoPosition({ left: 2, top: 100, bottom: 120 }, vp).left, 8)
})

test('picks the roomier side when neither has the minimum', () => {
  const small = { width: 400, height: 300 }
  assert.ok('top' in infoPosition({ left: 50, top: 60, bottom: 80 }, small))
  assert.ok('bottom' in infoPosition({ left: 50, top: 200, bottom: 220 }, small))
})
