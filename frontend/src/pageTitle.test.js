import test from 'node:test'
import assert from 'node:assert/strict'
import { titleUrl } from './pageTitle.js'

test('the path is what the title depends on', () => {
  assert.equal(titleUrl('/player/8478402', ''), '/player/8478402')
  assert.equal(titleUrl('/skaters', '?sort=goals&page=2'), '/skaters')
  assert.equal(titleUrl('/team/EDM', '?tab=roster'), '/team/EDM')
})

test('a comparison keeps its players, because they are in its title', () => {
  assert.equal(titleUrl('/compare', '?ids=1,2&metric=points'), '/compare?ids=1,2&metric=points')
  assert.equal(titleUrl('/compare', ''), '/compare')
})
