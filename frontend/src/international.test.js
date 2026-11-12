import test from 'node:test'
import assert from 'node:assert/strict'
import { hasBronze, medalText, resultLabel, tournamentName } from './international.js'

test('the Canada Cup became the World Cup of Hockey in 1996', () => {
  assert.equal(tournamentName({ tournament: 'worldcup', year: 1987, label: 'x' }), 'Canada Cup')
  assert.equal(tournamentName({ tournament: 'worldcup', year: 1996, label: 'x' }), 'World Cup of Hockey')
  assert.equal(tournamentName({ tournament: 'olympics', year: 2014, label: 'Olympic Games' }), 'Olympic Games')
})

test('medals are named, and finals-only tournaments have champions and runners-up', () => {
  assert.equal(resultLabel({ tournament: 'olympics', medal: 'gold' }), 'Gold')
  assert.equal(resultLabel({ tournament: 'worlds', medal: 'bronze' }), 'Bronze')
  assert.equal(resultLabel({ tournament: 'fournations', medal: 'gold' }), 'Champion')
  assert.equal(resultLabel({ tournament: 'worldcup', medal: 'silver' }), 'Runner-up')
  assert.equal(resultLabel({ tournament: 'olympics', medal: null }), 'Played')
})

test('medal text leaves out zeros', () => {
  assert.equal(medalText({ gold: 3, silver: 0, bronze: 1 }), '3 gold, 1 bronze')
  assert.equal(medalText({ gold: 0, silver: 0, bronze: 0 }), '')
})

test('which tournaments have a bronze', () => {
  assert.equal(hasBronze('olympics'), true)
  assert.equal(hasBronze('worldcup'), false)
  assert.equal(hasBronze('fournations'), false)
})
