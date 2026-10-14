import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const pct = (p) => `${Math.round(p * 100)}%`
const time = (iso) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }) : '')

function Side({ side }) {
  const [top, ...rest] = side.candidates
  return (
    <div className="pg-side">
      <Link to={`/team/${side.team}`} className="pg-team">{side.team}</Link>
      {top ? (
        <>
          <Link to={`/goalie/${top.player_id}`}>{top.name}</Link>
          {side.confirmed
            ? <span className="accent">Confirmed</span>
            : <span className={top.probability >= 0.7 ? 'accent' : 'muted'}>{pct(top.probability)}</span>}
          {rest[0] && <small>{rest[0].name.split(' ').slice(-1)[0]} {pct(rest[0].probability)}</small>}
        </>
      ) : <span className="muted">No data</span>}
      {side.back_to_back && !side.confirmed && <small>back-to-back</small>}
    </div>
  )
}

/** Today's games with each team's likely starting goalie: a guess until the NHL confirms the starter. */
export default function ProbableGoalies() {
  const [data, setData] = useState(null)
  useEffect(() => {
    let ignore = false
    fetch('/api/probable-goalies')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => !ignore && setData(d))
      .catch(() => {})
    return () => { ignore = true }
  }, [])
  if (!data || data.games.length === 0) return null

  return (
    <section aria-label="Probable goalies">
      <h2>Probable goalies</h2>
      <p className="muted">
        Percentages are a guess from each team's recent starts and back-to-backs. Once the NHL publishes the
        starter, usually near puck drop, it replaces the guess and is marked Confirmed.
      </p>
      <div className="pg-games">
        {data.games.map((g) => (
          <div key={g.game_id} className="pg-game">
            <Side side={g.away_goalies} />
            <Side side={g.home_goalies} />
            <em>{g.state === 'FUT' || g.state === 'PRE' ? time(g.start_time) : <Link to={`/game/${g.game_id}`}>Box score</Link>}</em>
          </div>
        ))}
      </div>
    </section>
  )
}
