import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const POLL_MS = 30000
const periodLabel = (g) => {
  if (g.period_type === 'SO') return 'Shootout'
  if (g.period_type === 'OT') return g.period > 4 ? `${g.period - 3}OT` : 'OT'
  return ['', '1st', '2nd', '3rd'][g.period] ?? ''
}

/** Scores for games in progress right now; renders nothing when no game is live. */
export default function LiveGames() {
  const [games, setGames] = useState([])
  useEffect(() => {
    let ignore = false
    const load = () =>
      fetch('/api/live')
        .then((r) => (r.ok ? r.json() : { games: [] }))
        .then((d) => !ignore && setGames(d.games))
        .catch(() => {})
    load()
    const t = setInterval(load, POLL_MS)
    return () => { ignore = true; clearInterval(t) }
  }, [])
  if (games.length === 0) return null

  return (
    <section aria-label="Live games">
      <h2>Live now</h2>
      <div className="live-games">
        {games.map((g) => (
          <Link key={g.game_id} to={`/game/${g.game_id}`} className="live-card">
            <span>{g.away.abbrev} <strong>{g.away.score}</strong></span>
            <span>{g.home.abbrev} <strong>{g.home.score}</strong></span>
            <em>{g.intermission ? `End of ${periodLabel(g)}` : `${periodLabel(g)} · ${g.time_remaining ?? ''}`}</em>
            {g.away.shots != null && <small>Shots {g.away.shots}–{g.home.shots}</small>}
          </Link>
        ))}
      </div>
    </section>
  )
}
