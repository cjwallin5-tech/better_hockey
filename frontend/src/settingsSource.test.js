import test from 'node:test'
import assert from 'node:assert/strict'
import { leagueSettings, withLeague, withScoring } from './settingsSource.js'

const personalScoring = { goals: 3, assists: 2 }
const personalLeague = { teams: 12, format: 'points', slots: { C: 2, L: 2, R: 2, D: 4, G: 2 } }
const base = { personalScoring, personalLeague }

test('no active league: the account-wide settings', () => {
  assert.deepEqual(leagueSettings({ ...base, view: null }), { scoring: personalScoring, league: personalLeague, source: 'personal' })
})

test('a league with nothing set keeps the account settings but takes the league size', () => {
  const eff = leagueSettings({ ...base, view: { teams_allowed: 10, settings: {}, my_settings: null } })
  assert.equal(eff.source, 'account')
  assert.equal(eff.scoring, personalScoring)
  assert.equal(eff.league.teams, 10)
  assert.deepEqual(eff.league.slots, personalLeague.slots)
})

test("the owner's shared settings apply, filling any gap from the account", () => {
  const view = { teams_allowed: 14, settings: { format: 'categories', slots: { C: 1, D: 6 }, scoring: { goals: 1 } }, my_settings: null }
  const eff = leagueSettings({ ...base, view })
  assert.equal(eff.source, 'shared')
  assert.deepEqual(eff.scoring, { goals: 1 })
  assert.equal(eff.league.format, 'categories')
  assert.deepEqual(eff.league.slots, { C: 1, L: 2, R: 2, D: 6, G: 2 })
  assert.equal(eff.league.teams, 14)
})

test('a member’s own settings beat the shared ones', () => {
  const view = {
    teams_allowed: 14,
    settings: { format: 'categories', slots: { C: 1 }, scoring: { goals: 1 } },
    my_settings: { teams: 16, format: 'points', slots: { C: 3 }, scoring: { goals: 5 } },
  }
  const eff = leagueSettings({ ...base, view })
  assert.equal(eff.source, 'own')
  assert.deepEqual(eff.scoring, { goals: 5 })
  assert.equal(eff.league.format, 'points')
  assert.equal(eff.league.teams, 16)
  assert.equal(eff.league.slots.C, 3)
})

test('two leagues give two different answers from the same account settings', () => {
  const a = leagueSettings({ ...base, view: { teams_allowed: 10, settings: { scoring: { goals: 9 } }, my_settings: null } })
  const b = leagueSettings({ ...base, view: { teams_allowed: 16, settings: {}, my_settings: { scoring: { assists: 4 } } } })
  assert.deepEqual([a.scoring, a.league.teams], [{ goals: 9 }, 10])
  assert.deepEqual([b.scoring, b.league.teams], [{ assists: 4 }, 16])
})

test('the first edit saves everything that applies now, so later changes elsewhere do not shift the league', () => {
  const view = { teams_allowed: 14, settings: { scoring: { goals: 1 }, format: 'categories' }, my_settings: null }
  const eff = leagueSettings({ ...base, view })
  const saved = withScoring(eff, view, { goals: 7 })
  assert.deepEqual(saved.scoring, { goals: 7 })
  assert.equal(saved.format, 'categories')
  assert.equal(saved.teams, 14)
  assert.deepEqual(saved.slots, { C: 2, L: 2, R: 2, D: 4, G: 2 })
})

test('later edits change only the edited part of the member’s own settings', () => {
  const own = { teams: 16, format: 'points', slots: { C: 3, L: 2, R: 2, D: 4, G: 2 }, scoring: { goals: 5 }, categories: { skater: ['goals'], goalie: ['wins'] } }
  const view = { teams_allowed: 14, settings: {}, my_settings: own }
  const eff = leagueSettings({ ...base, view })
  assert.deepEqual(withScoring(eff, view, { goals: 6 }), { ...own, scoring: { goals: 6 } })
  const next = withLeague(eff, view, { ...eff.league, teams: 20, format: 'categories' })
  assert.equal(next.teams, 20)
  assert.equal(next.format, 'categories')
  assert.deepEqual(next.scoring, { goals: 5 })
})
