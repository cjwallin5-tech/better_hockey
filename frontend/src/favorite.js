import { useCallback, useEffect, useState } from 'react'
import { useAuth } from './auth.js'

// The team you follow most closely (My team): saved to your account, so it follows you to any device. This browser only keeps a cache of it.
// Storage can be unavailable (private windows, blocked site data), so every access is guarded and the app works without it.
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

const callAccount = async (method, body) => {
  const r = await fetch('/api/favorite-team', { method, headers: { 'content-type': 'application/json' }, body: body && JSON.stringify(body) })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.detail ?? `Request failed (${r.status})`)
  return data
}

// The account this browser's copy was last reconciled with: undefined before the first check, null while signed out.
let accountUser

/** The account's team is the truth; the copy in this browser is only a cache so the page does not flash while the account loads. */
async function reconcile() {
  try {
    const { team } = await callAccount('GET')
    if (team !== readFavorite()) writeFavorite(team)
  } catch {
    accountUser = undefined // try again the next time something asks
  }
}

function onAccountChange(userId) {
  if (userId === accountUser) return
  const previous = accountUser
  accountUser = userId
  // Signed out, or switched to another account: nothing from the last person may linger in this browser.
  if (previous != null || userId == null) writeFavorite(null)
  if (userId != null) reconcile()
}

/**
 * { favorite, setFavorite }: the team abbreviation (or null) and a setter that updates every component using this hook and the account.
 * My team is an account feature: signed out there is no team, and the setter does nothing.
 */
export function useFavoriteTeam() {
  const { user, ready } = useAuth()
  const userId = user?.email ?? null
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
  useEffect(() => {
    if (ready) onAccountChange(userId)
  }, [ready, userId])
  const setFavorite = useCallback((abbrev) => {
    if (userId == null) return
    writeFavorite(abbrev)
    callAccount('PUT', { team: abbrev ?? null }).catch(() => { accountUser = undefined })
  }, [userId])
  return { favorite: ready && userId == null ? null : favorite, setFavorite, signedIn: userId != null, ready }
}
