// Run with: npm test   (Node's built-in test runner; no extra packages)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { luckById, roleSize, scheduleByTeam, waiverRows } from './waiver.js'

const player = (id, extra = {}) => ({ player_id: id, name: `Player ${id}`, team: 'EDM', position: 'C', games_played: 10, ...extra })
const val = (value, group = 'C', groupRank = 50) => ({ value, group, groupRank })
const base = () => ({
  kind: 'skater',
  players: [
    player(1, { recent_pace: 90, point_pace: 60 }),
    player(2, { recent_pace: 50, point_pace: 60, games_out: 3 }),
    player(3, { position: 'D', recent_pace: 70, point_pace: 40 }),
    player(4, { name: 'Zed Owned' }),
    player(5, { games_played: 0 }),
  ],
  values: new Map([[1, val(30)], [2, val(20)], [3, val(25, 'D')], [4, val(99)], [5, val(1)]]),
  roles: new Map(),
  luck: new Map(),
  schedule: new Map(),
  roster: new Set([4]),
})
const ids = (rows) => rows.map((r) => r.id)

test('your roster and players with no games are left out; default sort is value', () => {
  assert.deepEqual(ids(waiverRows(base())), [1, 3, 2])
})

test('position filter: a group, or F for all forwards', () => {
  assert.deepEqual(ids(waiverRows({ ...base(), filters: { position: 'D' } })), [3])
  assert.deepEqual(ids(waiverRows({ ...base(), filters: { position: 'F' } })), [1, 2])
})

test('hideHurt drops players 2+ games out; search matches names', () => {
  assert.deepEqual(ids(waiverRows({ ...base(), filters: { hideHurt: true } })), [1, 3])
  assert.deepEqual(ids(waiverRows({ ...base(), filters: { search: 'player 3' } })), [3])
})

test('likelyAvailable drops the players a league of this size has probably rostered', () => {
  const b = base()
  b.values = new Map([[1, val(30, 'C', 5)], [2, val(20, 'C', 40)], [3, val(25, 'D', 100)], [4, val(99)], [5, val(1)]])
  // 12 teams x 2 C slots = 24; x 4 D slots = 48
  assert.deepEqual(ids(waiverRows({ ...b, filters: { likelyAvailable: true } })), [3, 2]) // player 1 (C rank 5) is probably owned
})

test('hottest sorts by recent pace and flags a hot stretch', () => {
  const rows = waiverRows({ ...base(), sort: 'form' })
  assert.deepEqual(ids(rows), [1, 3, 2])
  assert.equal(rows[0].hot, true) // 90 vs 60
  assert.equal(rows[2].hot, false)
})

test('rising role lists only promotions, biggest first', () => {
  const b = base()
  b.roles = new Map([
    [1, { direction: 'up', pp_share_delta: 0.1, ev_delta: 0 }],
    [2, { direction: 'up', pp_share_delta: 0.4, ev_delta: 0 }],
    [3, { direction: 'down', pp_share_delta: -0.3, ev_delta: 0 }],
  ])
  assert.deepEqual(ids(waiverRows({ ...b, sort: 'role' })), [2, 1])
  assert.equal(roleSize({ direction: 'down', pp_share_delta: 0.4 }), 0)
})

test('buy-low lists cold players with positive value, coldest first; small samples are ignored', () => {
  const b = base()
  b.luck = new Map([
    [1, { z: -1.8, flag: 'cold', enough: true }],
    [2, { z: -2.5, flag: 'cold', enough: true }],
    [3, { z: -3, flag: 'cold', enough: false }],
  ])
  assert.deepEqual(ids(waiverRows({ ...b, sort: 'buy' })), [2, 1])
})

test('most games sorts by games in the coming week, then value', () => {
  const b = base()
  b.schedule = new Map([['EDM', { games: 4, ratio: 1.05 }]])
  b.players[2] = player(3, { position: 'D', team: 'CGY' })
  b.schedule.set('CGY', { games: 2, ratio: 0.9 })
  const rows = waiverRows({ ...b, sort: 'games' })
  assert.deepEqual(ids(rows), [1, 2, 3])
  assert.equal(rows[0].games, 4)
})

test('goalies use recent goals saved above average as their form', () => {
  const rows = waiverRows({
    kind: 'goalie',
    players: [player(7, { position: 'G', recent_gsaa: 2.5 }), player(8, { position: 'G', recent_gsaa: -1 })],
    values: new Map([[7, val(5, 'G')], [8, val(9, 'G')]]),
    roles: new Map(), luck: new Map(), schedule: new Map(), roster: new Set(), sort: 'form',
  })
  assert.deepEqual(ids(rows), [7, 8])
  assert.equal(rows[0].hot, false)
})

test('scheduleByTeam counts games and averages the ratio; luckById prefers the history-adjusted figures', () => {
  const s = scheduleByTeam({ teams: [{ team: 'EDM', games: [{ skater_ratio: 1.0 }, { skater_ratio: 1.2 }] }, { team: 'CGY', games: [] }] })
  assert.equal(s.get('EDM').games, 2)
  assert.ok(Math.abs(s.get('EDM').ratio - 1.1) < 1e-9)
  assert.equal(s.get('CGY').ratio, null)
  const l = luckById({ rows: [{ player_id: 1, enough: true, points_z: 2, points_z_adj: 1, points_flag: 'hot', points_flag_adj: 'steady' }] })
  assert.deepEqual(l.get(1), { z: 1, flag: 'steady', enough: true })
})

test('with a league, players on other teams are known and can be hidden; the likely-owned guess is off', () => {
  const b = base()
  const taken = new Map([[1, 'Friends FC'], [3, 'Pat']])
  assert.deepEqual(ids(waiverRows({ ...b, taken })), [1, 3, 2])                        // shown, with who owns them
  assert.equal(waiverRows({ ...b, taken }).find((r) => r.id === 1).ownedBy, 'Friends FC')
  assert.equal(waiverRows({ ...b, taken }).find((r) => r.id === 2).ownedBy, null)
  assert.deepEqual(ids(waiverRows({ ...b, taken, filters: { hideTaken: true } })), [2])
  assert.ok(waiverRows({ ...b, taken }).every((r) => r.likelyOwned === false))
  assert.deepEqual(ids(waiverRows({ ...b, filters: { hideTaken: true } })), [1, 3, 2])   // no league: nothing to hide
})
