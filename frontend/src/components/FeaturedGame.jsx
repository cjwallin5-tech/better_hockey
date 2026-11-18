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
      <TeamMark abbrev={abbrev} size={124} />
      <Link to={`/team/${abbrev}`} className="feat-abbrev">{abbrev}</Link>
      <span className="feat-name">{name}</span>
      {win != null && <strong className="feat-win">{pct(win)}</strong>}
    </div>
  )
}

const NOT_STARTED = ['FUT', 'PRE']
const FINISHED = ['FINAL', 'OFF']
const periodLabel = (g) => {
  if (g.period_type === 'SO') return 'Shootout'
  if (g.period_type === 'OT') return g.period > 4 ? `${g.period - 3}OT` : 'OT'
  return ['', '1st', '2nd', '3rd'][g.period] ?? ''
}
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
export default function FeaturedGame({ selectedId = null, live = {}, onShown }) {
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

  const open = (games ?? []).filter((g) => NOT_STARTED.includes(g.state)).sort((a, b) => b.score - a.score)
  const yours = favorite ? open.find((g) => plays(g, favorite)) : null
  const picked = selectedId ? (games ?? []).find((g) => g.game_id === selectedId) : null
  const game = picked ?? yours ?? open[0] ?? null
  const shownId = game?.game_id ?? null
  useEffect(() => { onShown?.(shownId) }, [shownId, onShown])
  if (!games || !game) return null

  const l = live[game.game_id]
  const over = FINISHED.includes(game.state)
  const started = Boolean(l) || over
  const away = l ? l.away.score : game.away_score
  const home = l ? l.home.score : game.home_score
  const status = l ? (l.intermission ? `End of ${periodLabel(l)}` : `${periodLabel(l)} ${l.time_remaining ?? ''}`.trim()) : over ? 'Final' : null
  const isYours = !picked && yours && game === yours
  const note = !picked && favorite && !yours ? teamNote(games, favorite) : null
  const reasons = started ? [] : game.reasons.filter((r) => !r.startsWith('You follow'))
  const name = (side) => game[`${side}_info`]?.name ?? game[side]
  const label = picked ? (l ? 'Live now' : over ? 'Final' : 'Tonight') : isYours ? `${favorite} tonight` : 'Game of the night'
  return (
    <section className="featured" style={{ '--away': teamColor(game.away), '--home': teamColor(game.home) }} aria-label={label}>
      <div className="feat-top">
        <span className="feat-label">{label}</span>
        {note && <span className="feat-note">{note}</span>}
        <span className="feat-time">{status ?? startTime(game.start_time)}</span>
      </div>
      <div className="feat-main">
        <Side abbrev={game.away} name={name('away')} win={!started && game.home_win != null ? 1 - game.home_win : null} />
        <div className="feat-mid">
          {started ? (
            <>
              <span className="feat-score">{away ?? 0} <i>–</i> {home ?? 0}</span>
              {l?.away?.shots != null && <small>Shots {l.away.shots}–{l.home.shots}</small>}
            </>
          ) : (
            <>
              <span>@</span>
              {game.expected_goals != null && <small>{game.expected_goals.toFixed(1)} goals expected</small>}
            </>
          )}
        </div>
        <Side abbrev={game.home} name={name('home')} win={!started ? game.home_win : null} />
      </div>
      {!started && game.home_win != null && (
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
      <div className="feat-links">
        {started && <Link to={`/game/${game.game_id}`} className="feat-more">Game page →</Link>}
        <Link to="/games" className="feat-more">All games →</Link>
      </div>
    </section>
  )
}
