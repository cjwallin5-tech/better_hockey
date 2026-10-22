import { useEffect, useSyncExternalStore } from 'react'
import { useAuth } from './auth.js'

// The signed-in user's watchlist: players and teams followed in the daily email (kept on the server, not the browser).
//   status: 'off' (signed out) | 'loading' | 'ready' | 'error'
let state = { status: 'off', items: [], limit: 100, error: null }
const listeners = new Set()
const set = (patch) => {
  state = { ...state, ...patch }
  listeners.forEach((l) => l())
}

const sameItem = (a, b) => a.kind === b.kind && String(a.ref) === String(b.ref)

async function call(method, url, body) {
  const r = await fetch(url, { method, headers: { 'content-type': 'application/json' }, body: body && JSON.stringify(body) })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.detail ?? `Request failed (${r.status})`)
  return data
}

async function load() {
  set({ status: 'loading', error: null })
  try {
    const { items, limit } = await call('GET', '/api/watchlist')
    set({ status: 'ready', items, limit })
  } catch (e) {
    set({ status: 'error', error: e.message })
  }
}

/** Watchlist state and actions. Loads once per sign-in; adds and removes show at once and are undone if the server refuses. */
export function useWatchlist() {
  const { user, ready } = useAuth()
  const snap = useSyncExternalStore((cb) => (listeners.add(cb), () => listeners.delete(cb)), () => state)
  const userId = user?.email ?? null
  useEffect(() => {
    if (!ready) return
    if (userId == null) set({ status: 'off', items: [], error: null })
    else if (state.status === 'off' || state.status === 'error') load()
  }, [ready, userId])

  const has = (kind, ref) => snap.items.some((i) => sameItem(i, { kind, ref }))
  const toggle = async (kind, ref, name) => {
    const before = state.items
    const adding = !before.some((i) => sameItem(i, { kind, ref }))
    set({
      error: null,
      items: adding ? [...before, { kind, ref: String(ref), name }] : before.filter((i) => !sameItem(i, { kind, ref })),
    })
    try {
      if (adding) await call('POST', '/api/watchlist', { kind, ref: String(ref), name })
      else await call('DELETE', `/api/watchlist?kind=${kind}&ref=${encodeURIComponent(ref)}`)
    } catch (e) {
      set({ items: before, error: e.message })
    }
  }
  return { ...snap, signedIn: userId != null, has, toggle }
}
