import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import RestBadge from '../components/RestBadge.jsx'
import TeamMark from '../components/TeamMark.jsx'
import { teamColor } from '../teamColors.js'
import { useFantasy } from '../fantasy.js'
import { useWatchlist } from '../watchlist.js'
import { useUrlSync } from '../urlState.js'
import { notableTips } from '../matchupTip.js'
import { Skeleton } from '../components/Skeleton.jsx'

const startTime = (iso) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }) : 'time TBD')
const FINISHED = ['FINAL', 'OFF']
const pct = (p) => `${Math.round(p * 100)}%`

function Goalie({ g, team }) {
  return (
    <div className="tn-goalie">
      <span className="tn-goalie-team">{team}</span>
      {g?.name ? (
        <>
          {g.player_id ? <Link to={`/goalie/${g.player_id}`}>{g.name}</Link> : g.name}
          <em className={g.confirmed || g.probability >= 0.7 ? 'sure' : ''}>{g.confirmed ? 'Confirmed' : pct(g.probability)}</em>
          {g.back_to_back && <span className="badge warn" title="Second game in two nights">B2B</span>}
        </>
      ) : <span className="muted">Starter unclear</span>}
    </div>
  )
}

/** Goalie matchup tips: where a team's shots come from against where tonight's likely goalie leaks or is strong. Only notable mismatches show. */
function ShotFit({ fit }) {
  const tips = notableTips(fit)
  if (tips.length === 0) return <p className="muted">Goalie zones: no notable mismatch either way.</p>
  return (
    <div className="shotfit">
      {tips.map((t) => (
        <p key={t.team}>
          <strong>Goalie zones, {t.team}:</strong> {t.text}
          {t.uncertain && <span className="muted"> {t.goalie} is only {pct(t.probability)} likely to start, so this may change.</span>}
        </p>
      ))}
    </div>
  )
}

function Side({ abbrev, name, win }) {
  return (
    <div className="tn-side">
      <TeamMark abbrev={abbrev} size={44} />
      <Link to={`/team/${abbrev}`} className="tn-abbrev">{abbrev}</Link>
      <span className="tn-name">{name}</span>
      {win != null && <strong className="tn-win">{pct(win)}</strong>}
    </div>
  )
}

function GameCard({ g, rank }) {
  const finished = FINISHED.includes(g.state)
  const live = g.state === 'LIVE' || g.state === 'CRIT'
  const name = (side) => g[`${side}_info`]?.name ?? g[side]
  const homeWin = g.home_win
  const stars = [...g.stars.away, ...g.stars.home]
  return (
    <li className={`tn-card${live ? ' live' : ''}`} style={{ '--away': teamColor(g.away), '--home': teamColor(g.home) }}>
      <div className="tn-head">
        {rank != null && <span className="tn-rank">#{rank}</span>}
        <span className="tn-time">{startTime(g.start_time)}</span>
        {(finished || live) && <Link to={`/game/${g.game_id}`} className="tn-state">{finished ? 'Final' : 'Live'}</Link>}
        <span className="tn-rest">
          {['tired', 'edge'].includes(g.rest.away) && <><RestBadge kind={g.rest.away} /> {g.away}</>}{' '}
          {['tired', 'edge'].includes(g.rest.home) && <><RestBadge kind={g.rest.home} /> {g.home}</>}
        </span>
      </div>

      <div className="tn-matchup">
        <Side abbrev={g.away} name={name('away')} win={homeWin != null ? 1 - homeWin : null} />
        <div className="tn-mid">
          <span>@</span>
          {g.expected_goals != null && <small title="Expected total goals">{g.expected_goals.toFixed(1)} goals</small>}
        </div>
        <Side abbrev={g.home} name={name('home')} win={homeWin} />
      </div>
      {homeWin != null && (
        <div className="tn-bar" title="Win chance on paper">
          <span style={{ width: `${(1 - homeWin) * 100}%`, background: 'var(--away)' }} />
          <span style={{ width: `${homeWin * 100}%`, background: 'var(--home)' }} />
        </div>
      )}

      {g.reasons.length > 0
        ? <ul className="tn-reasons">{g.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        : <p className="muted tn-none">Nothing stands out on paper.</p>}

      {g.goalies && (
        <div className="tn-goalies">
          <Goalie g={g.goalies.away} team={g.away} />
          <Goalie g={g.goalies.home} team={g.home} />
        </div>
      )}
      {g.shot_fit && <ShotFit fit={g.shot_fit} />}
      {stars.length > 0 && (
        <div className="tn-stars">
          {stars.map((st) => (
            <Link key={st.player_id} to={`/player/${st.player_id}`} className="tn-star">
              {st.name} <span>{st.points} P in {st.games_played}</span>
            </Link>
          ))}
        </div>
      )}
    </li>
  )
}

/** Tonight's games ranked by how worth watching they are for you: closeness, scoring, the playoff race, stars, your players. */
export default function Tonight() {
  const initial = new URLSearchParams(window.location.search)
  const [sort, setSort] = useState(initial.get('sort') === 'time' ? 'time' : 'interest')
  const [date, setDate] = useState(initial.get('date') ?? '')
  useUrlSync([['sort', sort, 'interest'], ['date', date, '']])
  const { list } = useFantasy()
  const watch = useWatchlist()
  const [state, setState] = useState({ key: null, data: null, error: null })

  const ids = useMemo(() => {
    const set = new Set(list.players.map((p) => p.id))
    for (const i of watch.items) if (i.kind === 'player') set.add(Number(i.ref))
    return [...set].filter(Number.isInteger)
  }, [list.players, watch.items])
  const teams = useMemo(() => watch.items.filter((i) => i.kind === 'team').map((i) => i.ref), [watch.items])
  const key = `${date}|${ids.join(',')}|${teams.join(',')}`

  useEffect(() => {
    let ignore = false
    const q = new URLSearchParams()
    if (date) q.set('date', date)
    if (ids.length) q.set('ids', ids.join(','))
    if (teams.length) q.set('teams', teams.join(','))
    fetch(`/api/tonight?${q}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`API returned ${r.status}`))))
      .then((data) => !ignore && setState({ key, data, error: null }))
      .catch((error) => !ignore && setState({ key, data: null, error: error.message }))
    return () => { ignore = true }
  }, [key, date, ids, teams])

  const { data, error } = state.key === key ? state : { data: null, error: null }
  const games = useMemo(() => {
    if (!data) return []
    const rows = [...data.games]
    if (sort === 'time') return rows
    return rows.sort((a, b) => b.score - a.score || (a.start_time ?? '').localeCompare(b.start_time ?? ''))
  }, [data, sort])

  return (
    <main>
      <header>
        <h1>What to watch</h1>
        <p>
          The day's games ranked by how much they're worth your attention: how even the teams are, how many goals to expect, the
          playoff race, star scorers, and your own roster and watchlist players. The weights are judgment calls, not a measurement,
          so use it to sort the night, not to predict it. {watch.signedIn || list.players.length ? '' : 'Add players to your fantasy team or watchlist to see your own players here.'}
        </p>
      </header>
      <div className="h2h-picks">
        <label className="h2h-pick">Sort by
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="interest">Most worth watching</option>
            <option value="time">Start time</option>
          </select>
        </label>
        <label className="h2h-pick">Date
          <input type="date" value={date || data?.date || ''} onChange={(e) => setDate(e.target.value)} />
        </label>
      </div>
      {error && <p className="status">{error}</p>}
      {!data && !error && <Skeleton />}
      {data && games.length === 0 && <p className="status">No games on {data.date}.</p>}
      {games.length > 0 && (
        <ul className="tn-list">
          {games.map((g, i) => <GameCard key={g.game_id} g={g} rank={sort === 'interest' ? i + 1 : null} />)}
        </ul>
      )}
      {games.some((g) => g.shot_fit) && (
        <p className="sub">
          Goalie zones compares where a team's shots come from (its nine ice zones, this season and last) with where the likely goalie
          has been beaten more or less than an average goalie over the last several seasons, shrunk toward average because a goalie's
          zone record is thin. The number is the goals per game that the mismatch is worth to the shooting team, on top of the goalie's
          overall level. In a test on four seasons, using only earlier seasons, this carried real but small signal: a typical mismatch is
          about 0.1 goals, and only those of 0.1 or more are shown. It also depends on who starts, and part of a goalie's weak zones
          may be his team's defensive habits rather than him.
        </p>
      )}
    </main>
  )
}
