import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { describe } from './glossary.js'

test('plain abbreviations are explained', () => {
  assert.match(describe('P'), /Points/)
  assert.match(describe('SV%'), /Save percentage/)
})

test('rolling-window and pace labels are explained from their base term', () => {
  assert.match(describe('L10 CF%'), /^Last 10 games: corsi for percentage/)
  assert.match(describe('L5 CF% vs season'), /compared with the season/)
  assert.match(describe('L5 Pace'), /last 5 games/)
  assert.match(describe('Pace (82)'), /82-game/)
})

test('unknown labels get no tooltip', () => {
  assert.equal(describe('Nonsense'), undefined)
})

test('every static column label on the leaderboards has a tooltip', () => {
  const missing = []
  for (const f of ['pages/Leaderboard.jsx', 'pages/Goalies.jsx', 'pages/AllTime.jsx']) {
    const src = readFileSync(new URL(f, import.meta.url), 'utf8')
    for (const [, label] of src.matchAll(/label: '([^']+)'/g)) {
      if (!describe(label) && !['Player', 'Goalie', 'Scoring', 'Defense', 'Possession', 'Special teams & usage', 'Overview', 'Strength splits', 'Hits & giveaways', 'Shooting', 'Era-adjusted', 'Special teams & goals', 'Record', 'Country', 'Debut season'].includes(label)) missing.push(`${f}: ${label}`)
    }
  }
  assert.deepEqual(missing, [])
})
