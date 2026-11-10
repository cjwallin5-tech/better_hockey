import { useCallback, useMemo } from 'react'
import { useFantasy } from './fantasy.js'
import { setLeagueRoster, toggleLeaguePlayer, useLeagues } from './leagues.js'
import { rosterSource } from './rosterSource.js'

/**
 * The roster you are working on, with the same shape as useFantasy() plus `source` (see rosterSource.js). With a league active that
 * has its own roster for you, reads and writes go to that league's roster; otherwise to your personal roster as before.
 * While the leagues load, changes are ignored so a click can't land on the wrong roster.
 */
export function useRoster() {
  const personal = useFantasy()
  const leagues = useLeagues()
  const source = rosterSource({ signedIn: leagues.signedIn, status: leagues.status, active: leagues.active })
  const onLeague = source.kind === 'league'
  const loading = source.kind === 'loading'
  const leaguePlayers = onLeague ? source.players : null
  const list = useMemo(() => (leaguePlayers ? { players: leaguePlayers } : personal.list), [leaguePlayers, personal.list])
  const hasPlayer = useCallback((id) => list.players.some((p) => p.id === id), [list])
  const togglePlayer = useCallback((player) => {
    if (loading) return
    if (onLeague) toggleLeaguePlayer(player)
    else personal.togglePlayer(player)
  }, [loading, onLeague, personal])
  const replacePlayers = useCallback((players) => {
    if (loading) return
    if (onLeague) setLeagueRoster(players)
    else personal.replacePlayers(players)
  }, [loading, onLeague, personal])
  return { list, hasPlayer, togglePlayer, replacePlayers, source, personalCount: personal.list.players.length }
}
