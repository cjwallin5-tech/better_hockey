import { useEffect, useSyncExternalStore } from 'react'
import { useAuth } from './auth.js'

// Private fantasy leagues: friends share rosters so the site can see who is taken (see backend/leagues.py).
// The league you are working in ("active") is remembered in this browser; its teams and rosters come from the server.
//   status: 'off' (signed out) | 'loading' | 'ready' | 'error'
const ACTIVE_KEY = 'nhl-stats.active-league'
let state = { status: 'off', leagues: [], activeId: null, active: null, error: null }
const listeners = new Set()
const set = (patch) => {
  state = { ...state, ...patch }
  listeners.forEach((l) => l())
}

function savedActive() {
  try {
    const v = Number(localStorage.getItem(ACTIVE_KEY))
    return Number.isInteger(v) && v > 0 ? v : null
  } catch {
    return null
  }
}

function saveActive(id) {
  try {
    if (id) localStorage.setItem(ACTIVE_KEY, String(id))
    else localStorage.removeItem(ACTIVE_KEY)
  } catch {
    // storage unavailable: the choice simply won't persist
  }
}

export async function call(method, url, body) {
  const r = await fetch(url, { method, headers: { 'content-type': 'application/json' }, body: body && JSON.stringify(body) })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.detail ?? `Request failed (${r.status})`)
  return data
}

async function loadActive(id) {
  if (!id) return set({ activeId: null, active: null })
  try {
    set({ activeId: id, active: await call('GET', `/api/leagues/${id}`) })
  } catch (e) {
    // the league is gone or we are no longer in it
    saveActive(null)
    set({ activeId: null, active: null, error: e.message })
  }
}

async function load() {
  set({ status: 'loading', error: null })
  try {
    const { leagues } = await call('GET', '/api/leagues')
    const saved = savedActive()
    const id = leagues.some((l) => l.id === saved) ? saved : leagues[0]?.id ?? null
    set({ status: 'ready', leagues })
    saveActive(id)
    await loadActive(id)
  } catch (e) {
    set({ status: 'error', error: e.message })
  }
}

/** Switch the league the Fantasy page works in (null for none). */
export function setActive(id) {
  saveActive(id)
  return loadActive(id)
}

/** Reload the league list and the active league's rosters. */
export const refresh = load

/** Create a league; it becomes the active one. body: { name, team_name, teams, settings }. */
export async function createLeague(body) {
  const detail = await call('POST', '/api/leagues', body)
  await load()
  await setActive(detail.id)
  return detail
}

/** Join with an invite code; the league becomes the active one. */
export async function joinLeague(code, teamName) {
  const detail = await call('POST', '/api/leagues/join', { code, team_name: teamName })
  await load()
  await setActive(detail.id)
  return detail
}

/** Run a change on a league (owner or member action) and keep the active league in step with the answer. */
export async function changeLeague(method, url, body) {
  const out = await call(method, url, body)
  if (out && out.teams && out.id === state.activeId) set({ active: out })
  return out
}

/** Leagues state and the active league. Loads once per sign-in. */
export function useLeagues() {
  const { user, ready } = useAuth()
  const snap = useSyncExternalStore((cb) => (listeners.add(cb), () => listeners.delete(cb)), () => state)
  const userId = user?.email ?? null
  useEffect(() => {
    if (!ready) return
    if (userId == null) set({ status: 'off', leagues: [], activeId: null, active: null, error: null })
    else if (state.status === 'off' || state.status === 'error') load()
  }, [ready, userId])
  return { ...snap, signedIn: userId != null }
}

/** Map player id -> team name for everyone on a team other than yours in the league, or null with no league. */
export function takenByOthers(league) {
  if (!league) return null
  const out = new Map()
  for (const t of league.teams) if (!t.mine) for (const p of t.players) out.set(p.id, t.name)
  return out
}
