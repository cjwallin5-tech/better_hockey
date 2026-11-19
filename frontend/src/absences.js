import { useEffect, useState } from 'react'
import { getJson } from './lists.js'
import { fmtToi, lastName } from './format.js'

// Who is out and who is covering for them, from /api/absences (see backend/absences.py). Plain functions so they can be tested.
// An absence is { player_id, name, team, position, games_out, role, teammates: [{ player_id, name, expected, seen }] }.
// What a teammate gains is what he actually got in the games missed once there are SEEN_MIN games of it, otherwise the average
// the backtest measured for his spot. Either way it is noisy from game to game, so it is shown as "about".

/** An absence has to be this many games old before the site calls the player out (one missed game is often a rest day). */
export const MIN_OUT = 2
/** Games a teammate needs in the absence before what he actually got outranks the average. */
export const SEEN_MIN = 2

/** The ice time a teammate gains a game, in seconds: { pp, total, games, observed }. */
export function gain(mate) {
  const observed = Boolean(mate.seen) && mate.seen.games >= SEEN_MIN
  const src = observed ? mate.seen : mate.expected
  return { pp: src.pp, total: src.total, games: observed ? mate.seen.games : 0, observed }
}

/** "+2:30" / "−0:45" for a change in seconds. */
export const signedTime = (sec) => (sec == null || !Number.isFinite(sec) ? '–' : `${sec < 0 ? '−' : '+'}${fmtToi(Math.round(Math.abs(sec)))}`)

/** The absence for this player (they are the one who is out), or null. */
export const absenceOf = (absences, playerId) => (absences ?? []).find((a) => a.player_id === playerId) ?? null

/** The best covering teammates for an absence, most gained first, only those who gained time. */
export function coverFor(absence, limit = 4) {
  return (absence?.teammates ?? [])
    .map((m) => ({ ...m, gain: gain(m) }))
    .filter((m) => m.gain.total > 0)
    .sort((a, b) => b.gain.total - a.gain.total || a.name.localeCompare(b.name))
    .slice(0, limit)
}

/** Absences this player is picking up minutes from: [{ absence, mate }], the biggest gain first. */
export function gainingFrom(absences, playerId) {
  const out = []
  for (const a of absences ?? []) {
    const m = a.teammates.find((t) => t.player_id === playerId)
    if (!m) continue
    const g = gain(m)
    if (g.total > 0) out.push({ absence: a, mate: m, gain: g })
  }
  return out.sort((a, b) => b.gain.total - a.gain.total)
}

/** Short text for a tooltip: "Covered by Lindell, Lundkvist", or null when nobody is clearly picking the time up. */
export function coverText(absence) {
  const names = coverFor(absence, 2).map((m) => lastName(m.name))
  return names.length ? `Covered by ${names.join(', ')}` : null
}

/** Map player id -> absence, for tables that badge many rows. */
export const absenceMap = (absences) => new Map((absences ?? []).map((a) => [a.player_id, a]))

/** Players who are out now (MIN_OUT games or more): [] when the feed is unavailable, null while loading. One shared request per minute (see lists.js). */
export function useAbsences() {
  const [list, setList] = useState(null)
  useEffect(() => {
    let ignore = false
    getJson('/api/absences').then((d) => !ignore && setList((d.absences ?? []).filter((a) => a.games_out >= MIN_OUT))).catch(() => !ignore && setList([]))
    return () => { ignore = true }
  }, [])
  return list
}
