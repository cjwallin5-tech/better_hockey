// Fetch hooks for a list of player ids, so each source is asked for once per roster (getJson shares and briefly caches the answer).
import { useEffect, useState } from 'react'
import { getJson } from './lists.js'

/** The JSON at `${url}?ids=...${query}` for a set of player ids: `null` until it has loaded for exactly this set, and `null` if it failed. */
export function useByIds(url, ids, query = '') {
  const list = [...new Set(ids)].sort((a, b) => a - b).join(',')
  const key = list + query
  const [state, setState] = useState({ key: null, data: null })
  useEffect(() => {
    if (!list) return undefined
    let ignore = false
    getJson(`${url}?ids=${list}${query}`)
      .then((data) => !ignore && setState({ key, data }))
      .catch(() => !ignore && setState({ key, data: null }))
    return () => { ignore = true }
  }, [url, list, query, key])
  return state.key === key ? state.data : null
}

/** Each rostered player's last 10 games (oldest first), keyed by id: { kind, games: [...] }. */
export const useRosterForm = (ids) => useByIds('/api/fantasy/form', ids)?.players ?? null

/** The coming week's games and lineup status for a roster: { from, to, players: { id: { team, games, games_out, traded } } }. */
export const useRosterWeek = (ids) => useByIds('/api/fantasy/week', ids)
