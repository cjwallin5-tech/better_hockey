import test from 'node:test'
import assert from 'node:assert/strict'
import { revealLeft, scrollState } from './tabScroll.js'

test('a row whose tabs all fit has nothing to hint at', () => {
  assert.equal(scrollState(0, 354, 354), 'none')
  assert.equal(scrollState(0, 354, 355), 'none')   // a pixel of rounding is not overflow
})

test('the fade follows where the hidden tabs are', () => {
  assert.equal(scrollState(0, 354, 603), 'start')
  assert.equal(scrollState(120, 354, 603), 'middle')
  assert.equal(scrollState(249, 354, 603), 'end')
  assert.equal(scrollState(248.4, 354, 603), 'end')    // sub-pixel scroll positions still count as the end
  assert.equal(scrollState(0.6, 354, 603), 'start')
})

const view = { viewWidth: 354, scrollWidth: 603 }

test('a tab already fully in view needs no scrolling', () => {
  assert.equal(revealLeft({ ...view, scrollLeft: 0, itemLeft: 10, itemWidth: 80 }), null)
  assert.equal(revealLeft({ ...view, scrollLeft: 100, itemLeft: 100, itemWidth: 80 }), null)   // flush with the left edge
  assert.equal(revealLeft({ ...view, scrollLeft: 0, itemLeft: 274, itemWidth: 80 }), null)     // flush with the right edge
})

test('a tab cut off on the right is scrolled to the middle', () => {
  const to = revealLeft({ ...view, scrollLeft: 0, itemLeft: 300, itemWidth: 100 })
  assert.equal(to, 300 - (354 - 100) / 2)
})

test('a tab cut off on the left is scrolled back into view', () => {
  const to = revealLeft({ ...view, scrollLeft: 200, itemLeft: 150, itemWidth: 100 })
  assert.equal(to, 23)   // centered would be 150 - 127
  assert.ok(to <= 150)
})

test('the target never goes past either end of the row', () => {
  assert.equal(revealLeft({ ...view, scrollLeft: 100, itemLeft: 2, itemWidth: 60 }), 0)                    // first tab: left end
  assert.equal(revealLeft({ ...view, scrollLeft: 0, itemLeft: 540, itemWidth: 60 }), 603 - 354)             // last tab: right end
})

test('a row that does not overflow never needs a target beyond zero', () => {
  assert.equal(revealLeft({ viewWidth: 400, scrollWidth: 300, scrollLeft: 0, itemLeft: 450, itemWidth: 50 }), 0)
})
