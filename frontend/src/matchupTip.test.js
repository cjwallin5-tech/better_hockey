import test from 'node:test'
import assert from 'node:assert/strict'
import { notableTips, tipSentence, zoneLabel } from './matchupTip.js'

const fit = (over = {}) => ({
  team: 'EDM', fit_goals: 0.12, goalie_goals: -0.15, shots_per_game: 25, notable: true,
  goalie: { name: 'Devin Cooley', probability: 0.66, confirmed: false },
  zones: [{ range: 'mid', lane: 'blocker', share: 0.16, league_share: 0.13, rate_per_100: 2.1, goals: 0.08 }], ...over,
})

test('zones read as a place on the ice', () => {
  assert.equal(zoneLabel({ range: 'mid', lane: 'blocker' }), 'mid-range, blocker side')
  assert.equal(zoneLabel({ range: 'close', lane: 'middle' }), 'close range through the middle')
})

test('a leaky zone is worded as a leak and a strong one as a strength', () => {
  const leak = tipSentence(fit())
  assert.match(leak, /Devin Cooley gives up \+2\.1 goals per 100 shots from mid-range, blocker side \(16% of their shots, 13% league-wide\)/)
  assert.match(leak, /against -0\.6 overall/)
  assert.match(leak, /Worth about \+0\.12 goals to EDM/)
  const strong = tipSentence(fit({ fit_goals: -0.12, zones: [{ range: 'long', lane: 'glove', share: 0.2, league_share: 0.15, rate_per_100: -1.5, goals: -0.08 }] }))
  assert.match(strong, /better than his average/)
  assert.match(strong, /-0\.12 goals to EDM/)
})

test('only notable fits are listed, biggest first, and an unlikely starter is marked', () => {
  const tips = notableTips({
    home_shooting: fit({ team: 'A', fit_goals: 0.11 }),
    away_shooting: fit({ team: 'B', fit_goals: -0.2, goalie: { name: 'X', probability: 0.5, confirmed: false } }),
  })
  assert.deepEqual(tips.map((t) => t.team), ['B', 'A'])
  assert.equal(tips[0].uncertain, true)
  assert.equal(tips[1].uncertain, false)
  assert.deepEqual(notableTips({ home_shooting: fit({ notable: false }) }), [])
  assert.deepEqual(notableTips(null), [])
})

test('a confirmed starter is never uncertain', () => {
  const [t] = notableTips({ a: fit({ goalie: { name: 'X', probability: 0.5, confirmed: true } }) })
  assert.equal(t.uncertain, false)
  assert.equal(t.confirmed, true)
})
