import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import TeamMark from './TeamMark.jsx'
import { teamColor } from '../teamColors.js'

const pct = (p) => `${Math.round(p * 100)}%`
const time = (iso) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }) : '')

function Row({ abbrev, side, score }) {
  const top = side?.candidates?.[0]
  const sure = side?.confirmed
  return (
    <div className="slate-row">
      <TeamMark abbrev={abbrev} size={30} />
      <Link to={`/team/${abbrev}`} className="slate-team">{abbrev}</Link>
      {score != null && <strong className="slate-score">{score}</strong>}
      {top && (
        <span className="slate-goalie" title={sure ? 'Confirmed starter' : 'Likely starter, a guess from recent starts and back-to-backs'}>
          {top.name}
          <em className={sure || top.probability >= 0.7 ? 'sure' : ''}>{sure ? 'Confirmed' : pct(top.probability)}</em>
        </span>
      )}
    </div>
  )
}

/** One card per game: both teams, the start time, and each side's likely goalie (a guess until the NHL confirms the starter). */
export default function Slate({ games }) {
  const [goalies, setGoalies] = useState({})
  useEffect(() => {
    let ignore = false
    fetch('/api/probable-goalies')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => !ignore && d && setGoalies(Object.fromEntries(d.games.map((g) => [g.game_id, g]))))
      .catch(() => {})
    return () => { ignore = true }
  }, [])

  return (
    <div className="slate">
      {games.map((g) => {
        const live = g.state === 'LIVE' || g.state === 'CRIT'
        const pg = goalies[g.game_id]
        return (
          <article key={g.game_id} className={`slate-card${live ? ' live' : ''}`} style={{ '--away': teamColor(g.away), '--home': teamColor(g.home) }}>
            <div className="slate-when">
              {live ? <Link to={`/game/${g.game_id}`}>Live</Link> : time(g.start_time)}
            </div>
            <Row abbrev={g.away} side={pg?.away_goalies} score={live ? g.away_score ?? 0 : null} />
            <Row abbrev={g.home} side={pg?.home_goalies} score={live ? g.home_score ?? 0 : null} />
          </article>
        )
      })}
    </div>
  )
}
