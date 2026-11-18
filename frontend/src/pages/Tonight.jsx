import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import RestBadge from '../components/RestBadge.jsx'
import TeamMark from '../components/TeamMark.jsx'
import { teamColor } from '../teamColors.js'
import { useRoster } from '../roster.js'
import { useWatchlist } from '../watchlist.js'
import { useFavoriteTeam } from '../favorite.js'
import { useUrlSync } from '../urlState.js'
import { notableTips } from '../matchupTip.js'
import { Skeleton } from '../components/Skeleton.jsx'
import { useLiveScores } from '../components/ScoreStrip.jsx'

const startTime = (iso) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }) : 'time TBD')
const FINISHED = ['FINAL', 'OFF']
const pct = (p) => `${Math.round(p * 100)}%`
const ET_TODAY = () => new Date().toLocaleDateString('en-CA', { timeZone: 'America/New_York' }) // the day the schedule is kept by
const addDays = (iso, n) => { const d = new Date(`${iso}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10) }
const weekday = (iso) => new Date(`${iso}T12:00:00Z`).toLocaleDateString(undefined, { weekday: 'short', timeZone: 'UTC' })
const monthDay = (iso) => new Date(`${iso}T12:00:00Z`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' })
const periodLabel = (g) => {
  if (g.period_type === 'SO') return 'Shootout'
  if (g.period_type === 'OT') return g.period > 4 ? `${g.period - 3}OT` : 'OT'
  return ['', '1st', '2nd', '3rd'][g.period] ?? ''
}

/** Day by day: step to the previous or next day, jump to any of the days around the one shown, or back to today. */
function DayNav({ current, today, onPick }) {
  const days = [-3, -2, -1, 0, 1, 2, 3].map((n) => addDays(current, n))
  return (
    <div className="day-nav" role="group" aria-label="Choose a day">
      <button type="button" className="day-step" onClick={() => onPick(addDays(current, -1))} aria-label="Previous day">‹</button>
      <div className="day-chips">
        {days.map((d) => (
          <button key={d} type="button" className={`day-chip${d === current ? ' on' : ''}${d === today ? ' today' : ''}`} aria-pressed={d === current} onClick={() => onPick(d)}>
            <span>{d === today ? 'Today' : weekday(d)}</span>
            <b>{monthDay(d)}</b>
          </button>
        ))}
      </div>
      <button type="button" className="day-step" onClick={() => onPick(addDays(current, 1))} aria-label="Next day">›</button>
      <input type="date" className="day-jump" value={current} onChange={(e) => e.target.value && onPick(e.target.value)} aria-label="Jump to a date" />
    </div>
  )
}

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

function GameCard({ g, mine, liveGame }) {  // mine: null, 'team' (the team you follow) or 'watch' (a team on your watchlist)
  const finished = FINISHED.includes(g.state)
  const live = Boolean(liveGame) || g.state === 'LIVE' || g.state === 'CRIT'
  const away = liveGame ? liveGame.away.score : g.away_score
  const home = liveGame ? liveGame.home.score : g.home_score
  const scored = (finished || live) && away != null && home != null
  const name = (side) => g[`${side}_info`]?.name ?? g[side]
  const homeWin = g.home_win
  const stars = [...g.stars.away, ...g.stars.home]
  return (
    <li className={`tn-card${live ? ' live' : ''}`} style={{ '--away': teamColor(g.away), '--home': teamColor(g.home) }}>
      <div className="tn-head">
        {mine && <span className="tn-rank tn-mine" title={mine === 'team' ? 'Your team plays in this game' : 'A team on your watchlist plays in this game'}>{mine === 'team' ? 'Your team' : 'Watchlist'}</span>}
        <span className="tn-time">{startTime(g.start_time)}</span>
        {(finished || live) && (
          <Link to={`/game/${g.game_id}`} className="tn-state">
            {finished ? 'Final' : liveGame ? (liveGame.intermission ? `End of ${periodLabel(liveGame)}` : `${periodLabel(liveGame)} ${liveGame.time_remaining ?? ''}`.trim()) : 'Live'}
          </Link>
        )}
        <span className="tn-rest">
          {['tired', 'edge'].includes(g.rest.away) && <><RestBadge kind={g.rest.away} /> {g.away}</>}{' '}
          {['tired', 'edge'].includes(g.rest.home) && <><RestBadge kind={g.rest.home} /> {g.home}</>}
        </span>
      </div>

      <div className="tn-matchup">
        <Side abbrev={g.away} name={name('away')} win={homeWin != null ? 1 - homeWin : null} />
        <div className="tn-mid">
          {scored ? <span className="tn-score">{away} <i>–</i> {home}</span> : <span>@</span>}
          {!scored && g.expected_goals != null && <small title="Expected total goals">{g.expected_goals.toFixed(1)} goals</small>}
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

/** Which of the teams you follow plays in a game: 'team' for the one set in My team, 'watch' for one on your watchlist, else null. */
const followedIn = (g, favorite, watched) => {
  if (favorite && (g.home === favorite || g.away === favorite)) return 'team'
  return watched.includes(g.home) || watched.includes(g.away) ? 'watch' : null
}

/** A day's games: your team's, then watchlist teams', then the rest, each by start time, each with scores once played and the reasons it is worth a look. */
export default function Tonight() {
  const initial = new URLSearchParams(window.location.search)
  const [date, setDate] = useState(initial.get('date') ?? '')
  const today = ET_TODAY()
  const current = date || today
  const { favorite } = useFavoriteTeam()
  const live = useLiveScores()
  useUrlSync([['date', date, '']])
  const { list } = useRoster()
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
    // `key` already holds the date, ids and teams: depending on the arrays themselves refetched whenever the watchlist finished loading
    // and rebuilt them with the same contents.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  const { data, error } = state.key === key ? state : { data: null, error: null }
  const games = useMemo(() => {
    if (!data) return []
    // your team's game, then watchlist teams' games, then the rest; each group by start time
    const tier = (g) => ({ team: 0, watch: 1 })[followedIn(g, favorite, teams)] ?? 2
    return [...data.games].sort((a, b) => tier(a) - tier(b) || String(a.start_time ?? '').localeCompare(String(b.start_time ?? '')) || a.game_id - b.game_id)
  }, [data, favorite, teams])

  return (
    <main>
      <header>
        <h1>Games</h1>
        <p>
          Every game by day, with your team's game first, then watchlist teams' games, then the rest, each by start time, with scores for the ones played. Each upcoming game lists what
          makes it worth a look: how even the teams are, how many goals to expect, the playoff race, star scorers, and your own roster and
          watchlist players. {watch.signedIn || list.players.length ? '' : 'Add players to your fantasy team or watchlist to see your own players here.'}
        </p>
      </header>
      <DayNav current={current} today={today} onPick={(d) => setDate(d === today ? '' : d)} />
      {error && <p className="status">{error}</p>}
      {!data && !error && <Skeleton />}
      {data && games.length === 0 && <p className="status">No games on {data.date}.</p>}
      {games.length > 0 && (
        <ul className="tn-list">
          {games.map((g) => <GameCard key={g.game_id} g={g} mine={followedIn(g, favorite, teams)} liveGame={live[g.game_id]} />)}
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
