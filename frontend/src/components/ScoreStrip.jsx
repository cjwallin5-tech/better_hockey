import { useEffect, useState } from 'react'
import TeamMark from './TeamMark.jsx'

const POLL_MS = 30000
const NOT_STARTED = ['FUT', 'PRE']
const FINISHED = ['FINAL', 'OFF']
const startTime = (iso) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }) : '')
const periodLabel = (g) => {
  if (g.period_type === 'SO') return 'SO'
  if (g.period_type === 'OT') return g.period > 4 ? `${g.period - 3}OT` : 'OT'
  return ['', '1st', '2nd', '3rd'][g.period] ?? ''
}

/** One team's line in a chip: logo, abbreviation, and the score once there is one. */
function Row({ abbrev, score, lead }) {
  return (
    <span className={`sc-row${lead ? ' lead' : ''}`}>
      <TeamMark abbrev={abbrev} size={18} />
      <b>{abbrev}</b>
      <em>{score ?? ''}</em>
    </span>
  )
}

/** Scores for games in progress, by game id, refreshed every 30 seconds. */
export function useLiveScores() {
  const [live, setLive] = useState({})
  useEffect(() => {
    let ignore = false
    const load = () =>
      fetch('/api/live')
        .then((r) => (r.ok ? r.json() : { games: [] }))
        .then((d) => !ignore && setLive(Object.fromEntries(d.games.map((g) => [g.game_id, g]))))
        .catch(() => {})
    load()
    const t = setInterval(load, POLL_MS)
    return () => { ignore = true; clearInterval(t) }
  }, [])
  return live
}

/**
 * Today's games in a thin scrolling strip: scores and the clock for games in progress, the final score once a game is over, the
 * puck-drop time before it. Choosing one puts it on show in the featured game above (it does not leave the page); `shownId` is the
 * game on show now. Renders nothing on a day without games.
 */
export default function ScoreStrip({ live, shownId, onSelect }) {
  const [day, setDay] = useState([])
  useEffect(() => {
    let ignore = false
    fetch('/api/tonight').then((r) => (r.ok ? r.json() : null)).then((d) => !ignore && d && setDay(d.games)).catch(() => {})
    return () => { ignore = true }
  }, [])

  if (day.length === 0) return null
  // in progress first, then what is still to come, then what is over
  const rank = (g) => (live[g.game_id] ? 0 : NOT_STARTED.includes(g.state) ? 1 : 2)
  const games = [...day].sort((a, b) => rank(a) - rank(b) || String(a.start_time).localeCompare(String(b.start_time)))

  return (
    <nav className="score-strip" aria-label="Today's games">
      {games.map((g) => {
        const l = live[g.game_id]
        const over = FINISHED.includes(g.state)
        const away = l ? l.away.score : over ? g.away_score : null
        const home = l ? l.home.score : over ? g.home_score : null
        const status = l
          ? (l.intermission ? `End ${periodLabel(l)}` : `${periodLabel(l)} ${l.time_remaining ?? ''}`)
          : over ? 'Final' : startTime(g.start_time)
        const on = g.game_id === shownId
        return (
          <button key={g.game_id} type="button" onClick={() => onSelect(g.game_id)} aria-pressed={on}
                  className={`score-chip${l ? ' is-live' : ''}${on ? ' on' : ''}`}>
            <span className="sc-status">{l && <i className="live-dot" aria-hidden="true" />}{status}</span>
            <Row abbrev={g.away} score={away} lead={away != null && home != null && away > home} />
            <Row abbrev={g.home} score={home} lead={away != null && home != null && home > away} />
          </button>
        )
      })}
    </nav>
  )
}
