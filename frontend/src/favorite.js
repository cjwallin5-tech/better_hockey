import { useCallback, useEffect, useState } from 'react'

// The team you follow most closely, kept in this browser only. Storage can be unavailable (private windows, blocked site
// data), so every access is guarded and the app works without it.
const KEY = 'nhl-stats.favorite-team'
const EVENT = 'favorite-team-changed'

export function readFavorite() {
  try {
    const v = localStorage.getItem(KEY)
    return v && /^[A-Z]{2,3}$/.test(v) ? v : null
  } catch {
    return null
  }
}

function writeFavorite(abbrev) {
  try {
    if (abbrev) localStorage.setItem(KEY, abbrev)
    else localStorage.removeItem(KEY)
  } catch {
    // storage unavailable: the choice simply won't persist
  }
  window.dispatchEvent(new Event(EVENT))
}

/** { favorite, setFavorite }: the team abbreviation (or null) and a setter that updates every component using this hook. */
export function useFavoriteTeam() {
  const [favorite, setState] = useState(readFavorite)
  useEffect(() => {
    const sync = () => setState(readFavorite())
    window.addEventListener(EVENT, sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener(EVENT, sync)
      window.removeEventListener('storage', sync)
    }
  }, [])
  const setFavorite = useCallback((abbrev) => writeFavorite(abbrev), [])
  return { favorite, setFavorite }
}
