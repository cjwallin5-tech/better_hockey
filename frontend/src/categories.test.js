// Run with: npm test   (Node's built-in test runner; no extra packages)
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { CATEGORY_PRESETS, cleanCategories } from './categoryDefs.js'
import { categoryValues, zScores } from './categories.js'
import { cleanLeague, tradeSummary } from './value.js'

const near = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} is not within ${eps} of ${b}`)
const sk = (id, goals, gp, extra = {}) => ({ player_id: id, position: 'C', team: 'AAA', games_played: gp, goals, assists: 0, ...extra })
const gk = (id, wins, gp, saves, shots, extra = {}) => ({ player_id: id, team: 'AAA', games_played: gp, wins, saves, shots_against: shots, goals_against: shots - saves, shutouts: 0, losses: gp - wins, ...extra })
const league = (teams, slots, skater, goalie = []) => ({
  teams, slots: { C: 0, L: 0, R: 0, D: 0, G: 0, ...slots }, format: 'categories', categories: { skater, goalie },
})

test('z-scores: the pool has mean 0 and spread 1, and a flat pool scores zero', () => {
  const z = zScores([1, 2, 3], [0, 1, 2])
  near(z[1], 0)
  near(z[0], -z[2])
  near(z.reduce((t, x) => t + x * x, 0) / 3, 1)
  assert.deepEqual(zScores([5, 5, 5], [0, 1, 2]), [0, 0, 0])
  assert.deepEqual(zScores([], []), [])
})

test('z-scores are measured against the pool, not everyone, and one freak is clamped', () => {
  const z = zScores([0, 1, 2, 100], [0, 1, 2])
  near(z[3], 6)                                  // far outside the pool but clamped
  assert.ok(z[2] > 1)
})

test('z-scores can be measured against a different spread than the values themselves', () => {
  const shrunk = [0.9, 1, 1.1]
  const plain = [0, 1, 2]
  const z = zScores(shrunk, [0, 1, 2], plain)
  near(z[2], 0.1 / Math.sqrt(2 / 3))             // the gap is 0.1, the real-outcome spread is sd(plain) = 0.816
  assert.ok(z[2] < zScores(shrunk, [0, 1, 2])[2])
})

test('a category that is mostly luck gets small z-scores next to a steady one', () => {
  // six goalies over 10 games each: shutouts bounce around (0 to 3), saves are steady volume (200 to 300)
  const goalies = [0, 1, 1, 2, 2, 3].map((so, i) => gk(i + 1, 5, 10, 200 + i * 20, 220 + i * 20, { shutouts: so }))
  const v = categoryValues({ skaters: [], goalies, league: league(1, { G: 1 }, [], ['shutouts', 'saves']) })
  const peak = (key) => Math.max(...[...v.values()].map((p) => Math.abs(p.z[key])))
  assert.ok(peak('shutouts') < 0.5 * peak('saves'), `shutouts ${peak('shutouts')} vs saves ${peak('saves')}`)
})

test('a goals league ranks by projected goals; the first non-starter is worth zero', () => {
  // 2 teams x 1 center slot: the third-best center is replacement level
  const skaters = [sk(1, 10, 10), sk(2, 8, 10), sk(3, 6, 10), sk(4, 4, 10), sk(5, 2, 10), sk(6, 0, 10)]
  const v = categoryValues({ skaters, goalies: [], league: league(2, { C: 1 }, ['goals']) })
  assert.deepEqual([1, 2, 3, 4, 5, 6].map((id) => v.get(id).groupRank), [1, 2, 3, 4, 5, 6])
  near(v.get(3).value, 0)
  assert.ok(v.get(1).value > v.get(2).value && v.get(2).value > 0)
  assert.ok(v.get(5).value < 0)
  assert.equal(v.get(1).overallRank, 1)
  near(v.get(1).zsum, v.get(1).z.goals)
})

test('a lower-is-better category flips the sign', () => {
  const skaters = [sk(1, 0, 10, { giveaways: 2 }), sk(2, 0, 10, { giveaways: 10 }), sk(3, 0, 10, { giveaways: 6 })]
  const v = categoryValues({ skaters, goalies: [], league: league(1, { C: 1 }, ['giveaways']) })
  assert.ok(v.get(1).z.giveaways > 0)             // few giveaways is good
  assert.ok(v.get(2).z.giveaways < 0)
})

test('categories add up, and one you do not count adds nothing', () => {
  const skaters = [sk(1, 10, 10, { hits: 0 }), sk(2, 0, 10, { hits: 40 }), sk(3, 5, 10, { hits: 20 })]
  const both = categoryValues({ skaters, goalies: [], league: league(1, { C: 1 }, ['goals', 'hits']) })
  const goalsOnly = categoryValues({ skaters, goalies: [], league: league(1, { C: 1 }, ['goals']) })
  near(both.get(2).zsum, both.get(2).z.goals + both.get(2).z.hits)
  assert.ok(both.get(2).zsum > goalsOnly.get(2).zsum, 'hits help the hits player once they count')
  assert.equal(Object.keys(goalsOnly.get(2).z).join(), 'goals')
})

test('a category with nothing counted values everyone at zero', () => {
  const v = categoryValues({ skaters: [sk(1, 10, 10), sk(2, 0, 10)], goalies: [], league: league(1, { C: 1 }, []) })
  assert.equal(v.get(1).value, 0)
  assert.equal(v.get(2).value, 0)
})

test('games left count: the same player with more games left is worth more', () => {
  const skaters = [sk(1, 10, 10, { team: 'AAA' }), sk(2, 10, 10, { team: 'BBB' }), sk(3, 2, 10, { team: 'AAA' }), sk(4, 2, 10, { team: 'BBB' })]
  const gamesLeft = { AAA: { played: 10, left: 70 }, BBB: { played: 10, left: 35 } }
  const v = categoryValues({ skaters, goalies: [], league: league(1, { C: 1 }, ['goals']), gamesLeft })
  assert.ok(v.get(1).zsum > v.get(2).zsum)
  assert.equal(v.get(1).expectedGames, 70)
  assert.equal(v.get(2).expectedGames, 35)
})

test('goalie ratios are valued as saves and goals over the season, signs the right way round', () => {
  const goalies = [gk(10, 6, 8, 100, 110), gk(11, 3, 8, 90, 110), gk(12, 4, 8, 95, 110)]
  const cats = (c) => categoryValues({ skaters: [], goalies, league: league(1, { G: 1 }, [], c) })
  const sv = cats(['save_pct'])
  assert.ok(sv.get(10).z.save_pct > sv.get(12).z.save_pct && sv.get(12).z.save_pct > sv.get(11).z.save_pct)
  const gaa = cats(['gaa'])
  assert.ok(gaa.get(10).z.gaa > 0 && gaa.get(11).z.gaa < 0)     // fewer goals against is good
  const wins = cats(['wins'])
  assert.ok(wins.get(10).z.wins > wins.get(11).z.wins)
  const losses = cats(['losses'])
  assert.ok(losses.get(11).z.losses < losses.get(10).z.losses)  // more losses is bad
})

test('save percentage is pulled hard toward average: a tiny hot sample does not look like a star', () => {
  // 8 regular goalies at .900 over 800 shots, one with a perfect 20 shots
  const regulars = Array.from({ length: 8 }, (_, i) => gk(100 + i, 4, 20, 720, 800))
  const fluke = gk(1, 1, 1, 20, 20)
  const real = gk(2, 6, 20, 760, 800)                           // a genuinely good .950 over a full sample
  const v = categoryValues({ skaters: [], goalies: [fluke, real, ...regulars], league: league(1, { G: 1 }, [], ['save_pct']) })
  assert.ok(v.get(2).z.save_pct > v.get(1).z.save_pct)
  assert.ok(v.get(1).gp === 1)
})

test('skaters with a track record are pulled toward it for goals, others toward the average', () => {
  const regulars = Array.from({ length: 8 }, (_, i) => sk(100 + i, 5, 10))
  const slow = sk(1, 1, 5)
  const priors = { 1: { goals: 0.8, assists: 0.4 } }
  const withRecord = categoryValues({ skaters: [slow, ...regulars], goalies: [], league: league(1, { C: 1 }, ['goals']), priors })
  const without = categoryValues({ skaters: [slow, ...regulars], goalies: [], league: league(1, { C: 1 }, ['goals']) })
  assert.ok(withRecord.get(1).z.goals > without.get(1).z.goals)
  assert.equal(withRecord.get(1).hasHistory, true)
  assert.equal(without.get(1).hasHistory, false)
})

test('positions are compared with their own position for replacement level', () => {
  const skaters = [sk(1, 10, 10), sk(2, 5, 10), sk(3, 3, 10, { position: 'D' }), sk(4, 1, 10, { position: 'D' })]
  const v = categoryValues({ skaters, goalies: [], league: league(1, { C: 1, D: 1 }, ['goals']) })
  near(v.get(2).value, 0)                                        // the second center is replacement for centers
  near(v.get(4).value, 0)
  assert.ok(v.get(3).value > 0, 'the best defenseman has value despite scoring less than a center')
})

test('league settings: format and categories are validated', () => {
  assert.equal(cleanLeague({}).format, 'points')
  assert.equal(cleanLeague({ format: 'categories' }).format, 'categories')
  assert.equal(cleanLeague({ format: 'nonsense' }).format, 'points')
  assert.deepEqual(cleanLeague({}).categories, cleanCategories(null))
  assert.deepEqual(cleanCategories({ skater: ['hits', 'goals', 'nope'], goalie: ['gaa'] }), { skater: ['goals', 'hits'], goalie: ['gaa'] })
  assert.deepEqual(cleanCategories({ skater: [], goalie: [] }), { skater: [], goalie: [] })   // choosing none is allowed
  assert.deepEqual(cleanCategories({}).skater, CATEGORY_PRESETS['Yahoo-style'].skater)
})

test('a trade in a category league adds up each category on each side', () => {
  const skaters = [sk(1, 10, 10, { hits: 0 }), sk(2, 0, 10, { hits: 40 }), sk(3, 5, 10, { hits: 20 }), sk(4, 2, 10, { hits: 10 })]
  const v = categoryValues({ skaters, goalies: [], league: league(1, { C: 2 }, ['goals', 'hits']) })
  const t = tradeSummary([1], [2, 3], v)
  near(t.give.z.goals, v.get(1).z.goals)
  near(t.get.z.hits, v.get(2).z.hits + v.get(3).z.hits)
  near(t.net, v.get(2).value + v.get(3).value - v.get(1).value)
})
