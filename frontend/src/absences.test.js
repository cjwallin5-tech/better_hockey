import test from 'node:test'
import assert from 'node:assert/strict'
import { absenceMap, absenceOf, coverFor, coverText, gain, gainingFrom, signedTime } from './absences.js'

const mate = (id, name, expectedTotal, seen) => ({ player_id: id, name, expected: { ev: 0, pp: 0, total: expectedTotal }, seen })
const heiskanen = {
  player_id: 1, name: 'Miro Heiskanen', team: 'DAL', games_out: 5,
  teammates: [
    mate(2, 'Esa Lindell', 64, { games: 4, ev: 10, pp: 59, total: 150 }),
    mate(3, 'Nils Lundkvist', 64, { games: 4, ev: 117, pp: 8, total: 136 }),
    mate(4, 'Tyler Myers', 64, { games: 1, ev: 0, pp: 0, total: 300 }),   // one game: the average outranks it
    mate(5, 'Cold Defender', 5, { games: 4, ev: -30, pp: 0, total: -30 }),
  ],
}

test('gain uses what was seen once there are enough games, else the average', () => {
  assert.equal(gain(heiskanen.teammates[0]).total, 150)
  assert.equal(gain(heiskanen.teammates[0]).observed, true)
  assert.equal(gain(heiskanen.teammates[2]).total, 64)
  assert.equal(gain(heiskanen.teammates[2]).observed, false)
})

test('signedTime formats seconds with a sign', () => {
  assert.equal(signedTime(150), '+2:30')
  assert.equal(signedTime(-45), '−0:45')
  assert.equal(signedTime(null), '–')
})

test('coverFor lists the biggest gainers first and drops those who lost time', () => {
  assert.deepEqual(coverFor(heiskanen).map((m) => m.name), ['Esa Lindell', 'Nils Lundkvist', 'Tyler Myers'])
  assert.equal(coverFor(heiskanen, 1).length, 1)
  assert.deepEqual(coverFor(null), [])
})

test('absenceOf finds the player who is out', () => {
  assert.equal(absenceOf([heiskanen], 1), heiskanen)
  assert.equal(absenceOf([heiskanen], 2), null)
  assert.equal(absenceOf(null, 1), null)
})

test('gainingFrom finds the absences a teammate benefits from', () => {
  const r = gainingFrom([heiskanen], 2)
  assert.equal(r.length, 1)
  assert.equal(r[0].absence.name, 'Miro Heiskanen')
  assert.deepEqual(gainingFrom([heiskanen], 5), [])   // lost time, so not "gaining"
  assert.deepEqual(gainingFrom([heiskanen], 99), [])
})

test('coverText and absenceMap', () => {
  assert.equal(coverText(heiskanen), 'Covered by Lindell, Lundkvist')
  assert.equal(coverText({ teammates: [] }), null)
  assert.equal(absenceMap([heiskanen, { ...heiskanen, player_id: 9 }]).size, 2)
})
