import { useCallback, useEffect, useState } from 'react'

// Your fantasy roster, kept in this browser only. Storage can be unavailable (private windows,
// blocked site data), so every access is guarded and the app works without it. The key predates
// the fantasy page (it was a watchlist), so players starred earlier carry over.
const KEY = 'nhl-stats.watchlist'
export const FANTASY_EVENT = 'fantasy-changed'
const EVENT = FANTASY_EVENT
const EMPTY = { players: [] }

export function read() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? 'null')
    return { players: Array.isArray(raw?.players) ? raw.players : [] }
  } catch {
    return EMPTY
  }
}

export function write(next) {
  try {
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    // storage unavailable: the change simply won't persist
  }
  window.dispatchEvent(new Event(EVENT))
}

export function useFantasy() {
  const [list, setList] = useState(read)
  useEffect(() => {
    const sync = () => setList(read())
    window.addEventListener(EVENT, sync)
    window.addEventListener('storage', sync) // other tabs
    return () => {
      window.removeEventListener(EVENT, sync)
      window.removeEventListener('storage', sync)
    }
  }, [])

  const hasPlayer = useCallback((id) => list.players.some((p) => p.id === id), [list])
  const togglePlayer = useCallback((player) => {
    const cur = read()
    write({
      players: cur.players.some((p) => p.id === player.id)
        ? cur.players.filter((p) => p.id !== player.id)
        : [...cur.players, { id: player.id, kind: player.kind, name: player.name }],
    })
  }, [])

  const replacePlayers = useCallback((players) => write({ players }), [])

  return { list, hasPlayer, togglePlayer, replacePlayers }
}

// --- Sharing / backup: the roster and scoring packed into a link or a JSON file ------------------
const clean = (players) =>
  (Array.isArray(players) ? players : [])
    .filter((p) => p && Number.isInteger(p.id) && (p.kind === 'skater' || p.kind === 'goalie') && typeof p.name === 'string')
    .map((p) => ({ id: p.id, kind: p.kind, name: p.name }))

export function encodeShare(players, scoring) {
  const json = JSON.stringify({ p: players.map((x) => [x.id, x.kind === 'goalie' ? 'g' : 's', x.name]), s: scoring })
  return btoa(unescape(encodeURIComponent(json))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** { players, scoring } from a share-link value, or null if it isn't valid. */
export function decodeShare(text) {
  try {
    const b64 = text.replace(/-/g, '+').replace(/_/g, '/')
    const raw = JSON.parse(decodeURIComponent(escape(atob(b64))))
    const players = clean(raw.p.map(([id, k, name]) => ({ id, kind: k === 'g' ? 'goalie' : 'skater', name })))
    const scoring = raw.s && typeof raw.s === 'object' ? Object.fromEntries(Object.entries(raw.s).filter(([, v]) => Number.isFinite(Number(v)))) : {}
    return players.length ? { players, scoring } : null
  } catch {
    return null
  }
}

/** { players, scoring } from a backup file's text (see exportBackup), or null. */
export function parseBackup(text) {
  try {
    const raw = JSON.parse(text)
    const players = clean(raw.players)
    return players.length ? { players, scoring: raw.scoring && typeof raw.scoring === 'object' ? raw.scoring : {} } : null
  } catch {
    return null
  }
}
export const exportBackup = (players, scoring) => JSON.stringify({ app: 'nhl-stats-fantasy', version: 1, players, scoring }, null, 2)

// --- Scoring: points per unit of each stat, set by the user to match their league's rules --------
export const SKATER_CATS = [
  ['goals', 'Goal'], ['assists', 'Assist'], ['plus_minus', 'Plus/minus'], ['pim', 'Penalty minute'],
  ['pp_points', 'Power-play point (bonus)'], ['sh_points', 'Short-handed point (bonus)'],
  ['game_winning_goals', 'Game-winning goal'], ['shots', 'Shot on goal'], ['hits', 'Hit'],
  ['blocked_shots', 'Blocked shot'], ['takeaways', 'Takeaway'], ['giveaways', 'Giveaway'],
]
export const GOALIE_CATS = [
  ['wins', 'Win'], ['losses', 'Loss'], ['ot_losses', 'OT loss'], ['saves', 'Save'],
  ['goals_against', 'Goal against'], ['shutouts', 'Shutout'],
]

export const SCORING_PRESETS = {
  'Points only': { goals: 1, assists: 1 },
  'Standard': { goals: 3, assists: 2, plus_minus: 1, pp_points: 1, shots: 0.4, wins: 4, saves: 0.2, goals_against: -1, shutouts: 3 },
  'Categories-style': { goals: 3, assists: 2, plus_minus: 1, pim: 0.25, pp_points: 1, sh_points: 2, game_winning_goals: 1, shots: 0.5, hits: 0.25, blocked_shots: 0.5, wins: 4, saves: 0.2, goals_against: -2, shutouts: 3, ot_losses: 1 },
}

const SCORING_KEY = 'nhl-stats.fantasy-scoring'
export const SCORING_EVENT = 'fantasy-scoring-changed'

export function readScoring() {
  try {
    const raw = JSON.parse(localStorage.getItem(SCORING_KEY) ?? 'null')
    return raw && typeof raw === 'object' ? raw : SCORING_PRESETS['Points only']
  } catch {
    return SCORING_PRESETS['Points only']
  }
}

export function useScoring() {
  const [scoring, setScoringState] = useState(readScoring)
  useEffect(() => {
    const sync = () => setScoringState(readScoring())
    window.addEventListener(SCORING_EVENT, sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener(SCORING_EVENT, sync)
      window.removeEventListener('storage', sync)
    }
  }, [])
  const setScoring = useCallback((next) => {
    try {
      localStorage.setItem(SCORING_KEY, JSON.stringify(next))
    } catch {
      // storage unavailable: the change simply won't persist
    }
    window.dispatchEvent(new Event(SCORING_EVENT))
  }, [])
  return { scoring, setScoring }
}

/** Fantasy points for a season row under the given scoring; stats the row lacks count as 0. */
export const fantasyPoints = (row, cats, scoring) =>
  cats.reduce((t, [key]) => t + (row[key] ?? 0) * (Number(scoring[key]) || 0), 0)

/** Replace the whole local state (roster and scoring), e.g. with what's stored on the account. */
export function applyState({ players, scoring }) {
  write({ players: clean(players) })
  try {
    localStorage.setItem(SCORING_KEY, JSON.stringify(scoring ?? {}))
  } catch {
    // storage unavailable: the change simply won't persist
  }
  window.dispatchEvent(new Event(SCORING_EVENT))
}
