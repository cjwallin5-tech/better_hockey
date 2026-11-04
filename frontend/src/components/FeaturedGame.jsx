import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import TeamMark from './TeamMark.jsx'
import { useFavoriteTeam } from '../favorite.js'
import { teamColor } from '../teamColors.js'

const pct = (p) => `${Math.round(p * 100)}%`
const startTime = (iso) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }) : '')

function Side({ abbrev, name, win }) {
  return (
    <div className="feat-side">
      <TeamMark abbrev={abbrev} size={92} />
      <Link to={`/team/${abbrev}`} className="feat-abbrev">{abbrev}</Link>
      <span className="feat-name">{name}</span>
      {win != null && <strong className="feat-win">{pct(win)}</strong>}
    </div>
  )
}

const NOT_STARTED = ['FUT', 'PRE']
const plays = (g, team) => g.home === team || g.away === team

/** What happened to your team's night when its game is not the one on show. */
function teamNote(games, team) {
  const mine = games.find((g) => plays(g, team))
  if (!mine) return `${team} is off tonight.`
  if (NOT_STARTED.includes(mine.state)) return null
  return ['LIVE', 'CRIT'].includes(mine.state) ? `${team} is playing now.` : `${team} has already played.`
}

/**
 * One game drawn big. When the team you follow plays and hasn't started, that is the game; otherwise it is the day's most
 * worth-watching game that has not started (the ranking from the Tonight page): both teams, the win chances and why it is worth a look.
 */
export default function FeaturedGame() {
  const { favorite } = useFavoriteTeam()
  const [state, setState] = useState({ key: null, games: null })
  const key = favorite ?? ''
  useEffect(() => {
    let ignore = false
    fetch(`/api/tonight${favorite ? `?teams=${favorite}` : ''}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => !ignore && d && setState({ key, games: d.games }))
      .catch(() => {})
    return () => { ignore = true }
  }, [favorite, key])
  const games = state.key === key ? state.games : null
  if (!games) return null

  const open = games.filter((g) => NOT_STARTED.includes(g.state)).sort((a, b) => b.score - a.score)
  const yours = favorite ? open.find((g) => plays(g, favorite)) : null
  const game = yours ?? open[0]
  if (!game) return null
  const note = favorite && !yours ? teamNote(games, favorite) : null
  const reasons = game.reasons.filter((r) => !r.startsWith('You follow'))
  const name = (side) => game[`${side}_info`]?.name ?? game[side]
  return (
    <section className="featured" style={{ '--away': teamColor(game.away), '--home': teamColor(game.home) }} aria-label={yours ? 'Your team tonight' : 'Game of the night'}>
      <div className="feat-top">
        <span className="feat-label">{yours ? `${favorite} tonight` : 'Game of the night'}</span>
        {note && <span className="feat-note">{note}</span>}
        <span className="feat-time">{startTime(game.start_time)}</span>
      </div>
      <div className="feat-main">
        <Side abbrev={game.away} name={name('away')} win={game.home_win != null ? 1 - game.home_win : null} />
        <div className="feat-mid">
          <span>@</span>
          {game.expected_goals != null && <small>{game.expected_goals.toFixed(1)} goals expected</small>}
        </div>
        <Side abbrev={game.home} name={name('home')} win={game.home_win} />
      </div>
      {game.home_win != null && (
        <div className="tn-bar" title="Win chance on paper">
          <span style={{ width: `${(1 - game.home_win) * 100}%`, background: 'var(--away)' }} />
          <span style={{ width: `${game.home_win * 100}%`, background: 'var(--home)' }} />
        </div>
      )}
      {reasons.length > 0 && (
        <ul className="feat-reasons">
          {reasons.slice(0, 3).map((r) => <li key={r}>{r}</li>)}
        </ul>
      )}
      <Link to="/tonight" className="feat-more">All of tonight's games, ranked →</Link>
    </section>
  )
}
