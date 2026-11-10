import { useSyncExternalStore } from 'react'
import { FANTASY_EVENT, LEAGUE_EVENT, SCORING_EVENT, applyLeague, applyState, read, readLeague, readScoring } from './fantasy.js'
import { leagueShape, planReconcile, sameState } from './syncPlan.js'

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

// Only the league shape the Sunday email needs (slots, teams, format) is stored on the account; the rest of the local
// league settings stay in this browser. What to do when the two sides differ is decided in syncPlan.js.
const local = () => ({ players: read().players, scoring: readScoring(), league: leagueShape(readLeague()) })

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
  window.addEventListener(LEAGUE_EVENT, onChange)
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
    const plan = planReconcile(server, local())
    if (plan.roster === 'conflict') return set({ sync: 'conflict', server })
    if (plan.roster === 'download') applyState(server)
    else if (plan.league === 'download') applyLeague(server.league)
    // Upload after any download, so settings the account already has are never replaced by an empty league. (An account that has
    // never saved scoring gets this browser's.)
    if (plan.roster === 'upload' || plan.league === 'upload' || plan.scoring === 'upload') await send('/api/fantasy/state', 'PUT', local())
    set({ sync: 'synced', server: null })
    watchLocalChanges()
  } catch (e) {
    set({ sync: 'error', error: e.message })
  }
}

async function pull() {
  try {
    const server = await send('/api/fantasy/state', 'GET')
    const mine = local()
    if (!sameState(server, mine)) applyState(server)
    else if (planReconcile(server, mine).league === 'download') applyLeague(server.league)
  } catch {
    // offline or a transient error: keep what's here
  }
}

/** The user's answer to a conflict: 'account' keeps the account's roster, 'browser' uploads this browser's. */
export async function resolveConflict(choice) {
  try {
    if (choice === 'account') applyState(state.server)
    else {
      // Keep this browser's roster and scoring, but not an empty league over the account's saved one.
      if (planReconcile(state.server, local()).league === 'download') applyLeague(state.server.league)
      await send('/api/fantasy/state', 'PUT', local())
    }
    set({ sync: 'synced', server: null })
    watchLocalChanges()
  } catch (e) {
    set({ sync: 'error', error: e.message })
  }
}

export async function signIn(mode, email, password) {
  const { email: confirmed, admin } = await send(`/api/auth/${mode}`, 'POST', { email, password })
  set({ user: { email: confirmed, admin } })
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
