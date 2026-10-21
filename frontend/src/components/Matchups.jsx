import { useEffect, useState } from 'react'

/** How far from 1 a matchup ratio must be to count as soft or tough; mirrors LABEL_AT in backend/matchups.py. */
export const LABEL_AT = 0.04

/** 'soft', 'tough' or 'neutral' for a ratio where above 1 favors the player (the backend labels single games the same way). */
export const ratioLabel = (ratio) => (ratio >= 1 + LABEL_AT ? 'soft' : ratio <= 1 - LABEL_AT ? 'tough' : 'neutral')

/** Percent difference from average as text, e.g. 1.063 -> "+6%". */
export const pctOff = (ratio) => (ratio == null ? '–' : `${ratio >= 1 ? '+' : '−'}${Math.abs(Math.round((ratio - 1) * 100))}%`)

/** Team matchup ratings from /api/matchups/teams as a Map keyed by team abbreviation, or null until loaded. */
export function useMatchupTeams() {
  const [teams, setTeams] = useState(null)
  useEffect(() => {
    let ignore = false
    fetch('/api/matchups/teams')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => !ignore && setTeams(d ? new Map(d.teams.map((t) => [t.team, t])) : new Map()))
      .catch(() => !ignore && setTeams(new Map()))
    return () => { ignore = true }
  }, [])
  return teams
}

/** A small "soft" / "tough" tag for a matchup ratio (above 1 favors the player); nothing when it is about average. */
export function MatchupTag({ ratio, label, who = 'skaters' }) {
  if (!label || label === 'neutral') return null
  const soft = label === 'soft'
  const what = who === 'goalies' ? (soft ? 'a weaker offense' : 'a stronger offense') : (soft ? 'a leakier defense' : 'a tighter defense')
  return (
    <span className={soft ? 'badge' : 'badge warn'} title={`${soft ? 'Soft' : 'Tough'} matchup: ${pctOff(ratio)} vs an average opponent (${what}). Small, noisy differences early in the season.`}>
      {soft ? '▲ soft' : '▼ tough'}
    </span>
  )
}
