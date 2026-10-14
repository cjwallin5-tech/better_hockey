import { useSyncExternalStore } from 'react'
import { FANTASY_EVENT, SCORING_EVENT, applyState, read, readScoring } from './fantasy.js'

// Account + sync state, shared by the nav, the Account page and the Fantasy page.
//   sync: 'off' (signed out) | 'checking' | 'conflict' | 'synced' | 'error'
let state = { ready: false, user: null, sync: 'off', server: null, error: null }
const listeners = new Set()
const set = (patch) => {
  state = { ...state, ...patch }
  listeners.forEach((l) => l())
}
export const useAuth = () => useSyncExternalStore((cb) => (listeners.add(cb), () => listeners.delete(cb)), () => state)

const json = async (r) => {
  const body = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(body.detail ?? `Request failed (${r.status})`)
  return body
}
const send = (url, method, body) =>
  fetch(url, { method, headers: { 'content-type': 'application/json' }, body: body && JSON.stringify(body) }).then(json)

const local = () => ({ players: read().players, scoring: readScoring() })
const sameState = (a, b) =>
  JSON.stringify(a.players.map((p) => [p.id, p.kind])) === JSON.stringify(b.players.map((p) => [p.id, p.kind])) &&
  JSON.stringify(Object.entries(a.scoring).sort()) === JSON.stringify(Object.entries(b.scoring).sort())

let pushTimer = null
const push = () => {
  clearTimeout(pushTimer)
  pushTimer = setTimeout(() => {
    pushTimer = null
    send('/api/fantasy/state', 'PUT', local()).catch((e) => set({ sync: 'error', error: e.message }))
  }, 800)
}
let watching = false
function watchLocalChanges() {
  if (watching) return
  watching = true
  const onChange = () => state.sync === 'synced' && push()
  window.addEventListener(FANTASY_EVENT, onChange)
  window.addEventListener(SCORING_EVENT, onChange)
  // Pick up edits made on another device when coming back to this tab.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && state.sync === 'synced' && !pushTimer) pull()
  })
}

/** Compare this browser's roster with the account's and sync, or flag a conflict for the user. */
async function reconcile() {
  set({ sync: 'checking', error: null })
  try {
    const server = await send('/api/fantasy/state', 'GET')
    const mine = local()
    if (server.players.length === 0 && mine.players.length > 0) await send('/api/fantasy/state', 'PUT', mine)
    else if (server.players.length > 0 && mine.players.length === 0) applyState(server)
    else if (server.players.length > 0 && !sameState(server, mine)) return set({ sync: 'conflict', server })
    set({ sync: 'synced', server: null })
    watchLocalChanges()
  } catch (e) {
    set({ sync: 'error', error: e.message })
  }
}

async function pull() {
  try {
    const server = await send('/api/fantasy/state', 'GET')
    if (!sameState(server, local())) applyState(server)
  } catch {
    // offline or a transient error: keep what's here
  }
}

/** The user's answer to a conflict: 'account' keeps the account's roster, 'browser' uploads this browser's. */
export async function resolveConflict(choice) {
  try {
    if (choice === 'account') applyState(state.server)
    else await send('/api/fantasy/state', 'PUT', local())
    set({ sync: 'synced', server: null })
    watchLocalChanges()
  } catch (e) {
    set({ sync: 'error', error: e.message })
  }
}

export async function signIn(mode, email, password) {
  const { email: confirmed } = await send(`/api/auth/${mode}`, 'POST', { email, password })
  set({ user: { email: confirmed } })
  await reconcile()
}

export async function signOut() {
  await send('/api/auth/logout', 'POST').catch(() => {})
  clearTimeout(pushTimer)
  pushTimer = null
  set({ user: null, sync: 'off', server: null, error: null })
}

/** Call once at startup: finds out whether the browser already has a session. */
export function initAuth() {
  fetch('/api/auth/me')
    .then(json)
    .then(async ({ user }) => {
      set({ ready: true, user })
      if (user) await reconcile()
    })
    .catch(() => set({ ready: true }))
}
