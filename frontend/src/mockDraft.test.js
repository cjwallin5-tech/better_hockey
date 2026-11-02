import assert from 'node:assert/strict'
import { test } from 'node:test'
import { botPick, myPickReview, pickRng, rng, simulate, teamTotals, valueSpread } from './mockDraft.js'
import { slotAt } from './draft.js'

const SLOTS = { C: 1, L: 1, R: 1, D: 1, G: 1 }
const LEAGUE = { teams: 4, slots: SLOTS }

/** 6 players per position with falling values, so the board is C1 > L1 > ... interleaved by value. */
function makeBoard() {
  const rows = []
  let id = 1
  for (let i = 0; i < 6; i++) {
    for (const g of ['C', 'L', 'R', 'D', 'G']) rows.push({ id: id++, group: g, value: 100 - i * 12 - 'CLRDG'.indexOf(g), name: `${g}${i + 1}` })
  }
  rows.sort((a, b) => b.value - a.value || a.id - b.id)
  return rows.map((r, i) => ({ ...r, overall: i + 1 }))
}
const cfg = (over = {}) => ({ league: LEAGUE, slot: 2, snake: true, rounds: 5, seed: 7, noise: 'chalk', ...over })

test('the generator is deterministic and per-pick randomness ignores what came before', () => {
  const a = rng(5), b = rng(5)
  assert.deepEqual([a(), a(), a()], [b(), b(), b()])
  assert.ok([a(), a(), a()].every((v) => v >= 0 && v < 1))
  assert.equal(pickRng(9, 17)(), pickRng(9, 17)())
  assert.notEqual(pickRng(9, 17)(), pickRng(9, 18)())
  assert.notEqual(pickRng(9, 17)(), pickRng(10, 17)())
})

test('picks follow snake order, nobody is drafted twice, and it waits at your turn', () => {
  const board = makeBoard()
  const sim = simulate({ board, config: cfg() })
  assert.equal(sim.picks.length, 1)                  // team 1 picks, then it is slot 2 (you)
  assert.equal(sim.waiting, true)
  assert.equal(sim.onClock, 2)
  const full = simulate({ board, config: cfg({ slot: 1 }), userPicks: board.slice(0, 5).map((r) => r.id) })
  assert.ok(full.picks.every((p, i) => p.slot === slotAt(i + 1, 4, true)))
  assert.equal(new Set(full.picks.map((p) => p.id)).size, full.picks.length)
})

test('a chalk bot takes the best player it is allowed to', () => {
  const board = makeBoard()
  const first = simulate({ board, config: cfg() }).picks[0]
  assert.equal(first.id, board[0].id)
  assert.equal(first.bestLeft, board[0].value)
})

test('the whole draft is a function of the seed and your picks: replays match and undo is a prefix', () => {
  const board = makeBoard()
  const mine = []
  let sim = simulate({ board, config: cfg({ noise: 'realistic' }), userPicks: mine })
  while (!sim.done) {
    mine.push(sim.available[0].id)
    sim = simulate({ board, config: cfg({ noise: 'realistic' }), userPicks: mine })
  }
  const again = simulate({ board, config: cfg({ noise: 'realistic' }), userPicks: mine })
  assert.deepEqual(again.picks, sim.picks)
  const undone = simulate({ board, config: cfg({ noise: 'realistic' }), userPicks: mine.slice(0, -1) })
  assert.deepEqual(undone.picks, sim.picks.slice(0, undone.picks.length))
  assert.equal(undone.waiting, true)
})

test('noise changes bot picks with the seed, chalk does not', () => {
  const board = makeBoard()
  const picksFor = (seed, noise) => simulate({ board, config: cfg({ seed, noise, slot: 4 }), userPicks: [] }).picks.map((p) => p.id).join()
  assert.equal(picksFor(1, 'chalk'), picksFor(2, 'chalk'))
  const variants = new Set([1, 2, 3, 4, 5, 6, 7, 8].map((s) => picksFor(s, 'wild')))
  assert.ok(variants.size > 1)
})

test('every bot fills its starting slots, and a full draft leaves each team with the right number of players', () => {
  const board = makeBoard()
  const mine = []
  let sim = simulate({ board, config: cfg({ noise: 'wild' }) })
  while (!sim.done) {
    mine.push(sim.available.find((r) => true).id)
    sim = simulate({ board, config: cfg({ noise: 'wild' }), userPicks: mine })
  }
  for (let s = 1; s <= 4; s++) assert.equal(sim.rosters[s].length, 5)
  const totals = teamTotals(sim.rosters, SLOTS)
  for (const t of totals.filter((t) => t.slot !== 2)) assert.equal(t.missing, 0, `bot ${t.slot} left a starting slot empty`)
})

test('a pick that is not available is skipped, not applied', () => {
  const board = makeBoard()
  const sim = simulate({ board, config: cfg({ slot: 2 }), userPicks: [board[0].id, board[1].id] })   // the best player went to team 1
  assert.ok(!sim.applied.includes(board[0].id))
  assert.ok(sim.applied.includes(board[1].id))
})

test('a bot never stacks a position past its starters plus bench, unless forced', () => {
  const board = makeBoard()
  const held = ['G', 'G', 'G']   // one starter slot plus one goalie of bench is the limit
  const pick = botPick({ available: board, held, slots: SLOTS, picksLeft: 10, noise: 0, spread: 100, random: rng(1) })
  assert.notEqual(pick.group, 'G')
})

test('when only starting slots are left a bot takes a position it still needs', () => {
  const board = makeBoard()
  const held = ['C', 'L', 'R', 'D']   // only a goalie is missing, and one pick left
  const pick = botPick({ available: board, held, slots: SLOTS, picksLeft: 1, noise: 0, spread: 100, random: rng(1) })
  assert.equal(pick.group, 'G')
})

test('team totals add up each team\'s best starters and rank them', () => {
  const rosters = [[], [{ group: 'C', value: 50 }, { group: 'C', value: 40 }, { group: 'G', value: -5 }], [{ group: 'C', value: 30 }, { group: 'D', value: 20 }]]
  const t = teamTotals(rosters, { C: 1, L: 0, R: 0, D: 1, G: 1 })
  assert.equal(t[0].starters, 50)           // best C only; the goalie below the free pickup counts for 0; D missing
  assert.equal(t[0].missing, 1)
  assert.equal(t[1].starters, 50)
  assert.equal(t[1].missing, 1)
  assert.deepEqual(t.map((x) => x.rank), [1, 2])    // ties go to the lower slot
})

test('the pick review shows only your picks and what was left behind', () => {
  const picks = [{ n: 1, slot: 1, id: 1, value: 90, bestLeft: 90 }, { n: 2, slot: 2, id: 2, value: 70, bestLeft: 85 }, { n: 5, slot: 2, id: 3, value: 60, bestLeft: 60 }]
  const review = myPickReview(picks, 2)
  assert.deepEqual(review.map((r) => r.left), [15, 0])
})

test('the spread runs from the best player to about the last starter in the league', () => {
  const board = makeBoard()
  assert.equal(valueSpread(board, LEAGUE), board[0].value - board[19].value)
  assert.equal(valueSpread([], LEAGUE), 0)
})
