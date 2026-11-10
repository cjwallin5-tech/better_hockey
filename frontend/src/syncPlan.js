import { cleanLeague } from './value.js'

// Decides how this browser's fantasy state and the account's copy should be brought together. Pure, so it can be tested;
// auth.js does the fetching and writing. Both sides are { players, scoring, league }.
//
// The roster and the league settings are reconciled separately, so a device with a roster but no league settings can
// never upload "no league" over the settings the account already has.

/** The part of a league that is stored on the account (the rest of the local league settings stay in the browser). */
// Numbers saved as text (older browsers kept what was typed, "14") become numbers, which is all the account accepts.
const num = (v) => (v === undefined || v === null || v === '' ? undefined : Number(v))
export const leagueShape = (l) => ({
  teams: num(l?.teams),
  format: l?.format,
  slots: l?.slots && typeof l.slots === 'object' ? Object.fromEntries(Object.entries(l.slots).map(([g, v]) => [g, num(v)])) : undefined,
})

/** True when the league object carries any saved setting at all. */
export const hasLeague = (l) => {
  const s = leagueShape(l)
  return s.teams != null || s.format != null || s.slots != null
}

// Compared after cleaning, so a typed "24" equals 24 and slot order doesn't matter.
const normalLeague = (l) => {
  const c = cleanLeague(l)
  return JSON.stringify([c.teams, c.format, ...Object.keys(c.slots).sort().map((g) => [g, c.slots[g]])])
}
export const sameLeague = (a, b) => normalLeague(a) === normalLeague(b)

/** True when the account has scoring saved. An account that never saved any has `{}`, which means "nothing yet", not "blank". */
export const hasScoring = (s) => !!s && Object.keys(s).length > 0

/** Same roster and same scoring. `a` is the account's state: when it has no scoring saved, scoring can't differ (this browser's default
 *  scoring is not a conflict, and must not be replaced by nothing). */
export const sameState = (a, b) =>
  JSON.stringify(a.players.map((p) => [p.id, p.kind])) === JSON.stringify(b.players.map((p) => [p.id, p.kind])) &&
  (!hasScoring(a.scoring) || JSON.stringify(Object.entries(a.scoring).sort()) === JSON.stringify(Object.entries(b.scoring).sort()))

/**
 * { roster, league, scoring }, each one of 'none' | 'upload' | 'download' (scoring is only ever 'none' or 'upload'), and roster can also
 * be 'conflict' (both sides have different rosters and the user has to choose). Scoring is uploaded only when the account has none
 * saved; an account without scoring never overwrites this browser's.
 * League: the account's settings win whenever it has some and they differ from this browser's, including when this
 * browser has none; this browser's are uploaded only when the account has none.
 */
export function planReconcile(server, mine) {
  let roster = 'none'
  if (server.players.length === 0 && mine.players.length > 0) roster = 'upload'
  else if (server.players.length > 0 && mine.players.length === 0) roster = 'download'
  else if (server.players.length > 0 && !sameState(server, mine)) roster = 'conflict'

  let league = 'none'
  if (hasLeague(server.league)) {
    if (!hasLeague(mine.league) || !sameLeague(server.league, mine.league)) league = 'download'
  } else if (hasLeague(mine.league)) league = 'upload'
  const scoring = !hasScoring(server.scoring) && hasScoring(mine.scoring) ? 'upload' : 'none'
  return { roster, league, scoring }
}
