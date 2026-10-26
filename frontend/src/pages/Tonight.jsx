import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import RestBadge from '../components/RestBadge.jsx'
import TeamLogo from '../components/TeamLogo.jsx'
import { useFantasy } from '../fantasy.js'
import { useWatchlist } from '../watchlist.js'
import { useUrlSync } from '../urlState.js'

const startTime = (iso) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }) : 'time TBD')
const FINISHED = ['FINAL', 'OFF']
const pct = (p) => `${Math.round(p * 100)}%`

function Goalie({ g, team }) {
  if (!g?.name) return <span className="muted">{team}: starter unclear</span>
  return (
    <span>
      {team}: {g.player_id ? <Link to={`/goalie/${g.player_id}`}>{g.name}</Link> : g.name}{' '}
      <span className={g.confirmed ? 'accent' : 'muted'}>{g.confirmed ? 'confirmed' : `likely, ${pct(g.probability)}`}</span>
      {g.back_to_back && <sup title="Second game in two nights"> B2B</sup>}
    </span>
  )
}

function GameCard({ g, rank }) {
  const finished = FINISHED.includes(g.state)
  const teamName = (side) => g[`${side}_info`]?.name ?? g[side]
  return (
    <li className="card" style={{ listStyle: 'none', marginBottom: 12 }}>
      <h3 style={{ marginTop: 0 }}>
        {rank != null && <span className="muted">#{rank} </span>}
        {g.away_info && <TeamLogo team={g.away_info} />} <Link to={`/team/${g.away}`}>{teamName('away')}</Link> @{' '}
        {g.home_info && <TeamLogo team={g.home_info} />} <Link to={`/team/${g.home}`}>{teamName('home')}</Link>
        <span className="muted"> · {startTime(g.start_time)}</span>
        {finished && <> · <Link to={`/game/${g.game_id}`}>Final</Link></>}
      </h3>
      {g.reasons.length > 0 ? (
        <ul className="roster-alerts">
          {g.reasons.map((r) => <li key={r}>{r}</li>)}
        </ul>
      ) : <p className="muted">Nothing stands out on paper.</p>}
      <p className="muted">
        {g.home_win != null && <>On paper: {g.home} {pct(g.home_win)}, {g.away} {pct(1 - g.home_win)}; about {g.expected_goals.toFixed(1)} goals. </>}
        <RestBadge kind={g.rest.away} /> {g.rest.away ? g.away : ''} <RestBadge kind={g.rest.home} /> {g.rest.home ? g.home : ''}
      </p>
      {g.goalies && (
        <p>
          Goalies: <Goalie g={g.goalies.away} team={g.away} /> · <Goalie g={g.goalies.home} team={g.home} />
        </p>
      )}
      {(g.stars.away.length > 0 || g.stars.home.length > 0) && (
        <p className="muted">
          Top scorers:{' '}
          {[...g.stars.away, ...g.stars.home].map((s, i) => (
            <span key={s.player_id}>{i > 0 && ' · '}<Link to={`/player/${s.player_id}`}>{s.name}</Link> {s.points} P in {s.games_played}</span>
          ))}
        </p>
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
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
      </div>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && games.length === 0 && <p className="status">No games on {data.date}.</p>}
      {games.length > 0 && (
        <ul style={{ padding: 0 }}>
          {games.map((g, i) => <GameCard key={g.game_id} g={g} rank={sort === 'interest' ? i + 1 : null} />)}
        </ul>
      )}
    </main>
  )
}
