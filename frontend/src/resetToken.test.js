import test from 'node:test'
import assert from 'node:assert/strict'
import { tokenFromSearch } from './resetToken.js'

test('reads the token from a query string, with or without the leading question mark', () => {
  assert.equal(tokenFromSearch('?token=abc-DEF_123'), 'abc-DEF_123')
  assert.equal(tokenFromSearch('token=abc'), 'abc')
})

test('reading is repeatable: the second read finds the same token', () => {
  const search = '?token=once'
  assert.equal(tokenFromSearch(search), tokenFromSearch(search))
})

test('no token, an empty one or no query string at all gives an empty string', () => {
  assert.equal(tokenFromSearch(''), '')
  assert.equal(tokenFromSearch('?other=1'), '')
  assert.equal(tokenFromSearch('?token='), '')
  assert.equal(tokenFromSearch(undefined), '')
})
