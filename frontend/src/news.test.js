import test from 'node:test'
import assert from 'node:assert/strict'
import { currentTeam, newsUrl, timeAgo } from './news.js'

const NOW = Date.parse('2026-11-10T12:00:00Z')
const ago = (sec) => new Date(NOW - sec * 1000).toISOString()

test('timeAgo steps from seconds to minutes, hours and days', () => {
  assert.equal(timeAgo(ago(20), NOW), 'just now')
  assert.equal(timeAgo(ago(12 * 60), NOW), '12 min ago')
  assert.equal(timeAgo(ago(3 * 3600 + 100), NOW), '3 hr ago')
  assert.equal(timeAgo(ago(86400), NOW), '1 day ago')
  assert.equal(timeAgo(ago(3 * 86400), NOW), '3 days ago')
})

test('timeAgo shows a date after a week, and tolerates a clock a little ahead or a bad value', () => {
  assert.match(timeAgo(ago(9 * 86400), NOW), /\d/)
  assert.doesNotMatch(timeAgo(ago(9 * 86400), NOW), /ago/)
  assert.equal(timeAgo(ago(-30), NOW), 'just now')
  assert.equal(timeAgo('nonsense', NOW), '')
})

test('newsUrl only includes the filters that are set', () => {
  assert.equal(newsUrl(), '/api/news')
  assert.equal(newsUrl({ team: 'EDM', top: true, limit: 10 }), '/api/news?team=EDM&top=true&limit=10')
  assert.equal(newsUrl({ player: 8478402 }), '/api/news?player=8478402')
  assert.equal(newsUrl({ top: false }), '/api/news')
})

test('currentTeam takes the last team of a traded player', () => {
  assert.equal(currentTeam('NJD,TOR'), 'TOR')
  assert.equal(currentTeam('EDM'), 'EDM')
  assert.equal(currentTeam(null), '')
})
