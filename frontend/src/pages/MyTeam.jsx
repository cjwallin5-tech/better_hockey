import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Schedule from '../components/Schedule.jsx'
import SpecialTeams from '../components/SpecialTeams.jsx'
import TeamLogo from '../components/TeamLogo.jsx'
import { useFavoriteTeam } from '../favorite.js'
import { fmt1 } from '../format.js'

const pct = (v) => (v == null ? '–' : `${Math.round(v * 100)}%`)
const day = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
const xg = (v) => (v == null ? '–' : v.toFixed(2))
const VERDICT = {
  ahead: 'Results are ahead of the play: the goals are going in more than the chances say they should, which tends not to last.',
  behind: 'Results are behind the play: the team is creating more than it is getting for it, so better results are likely if the play holds.',
  'in line': 'Results match the play: the goals are about what the chances say they should be.',
}

/** The two rolling shares as lines, with 50% (an even game) marked: xG share is the play, goal share the results. */
function ShareChart({ rolling, window }) {
  const pts = rolling.filter((r) => r.xg_share != null && r.goal_share != null)
  if (pts.length < 2) return null
  const W = 640, H = 220, M = { l: 40, r: 14, t: 12, b: 28 }
  const n = pts.length
  const x = (i) => M.l + (i / (n - 1)) * (W - M.l - M.r)
  const lo = Math.min(0.3, ...pts.flatMap((r) => [r.xg_share, r.goal_share])) - 0.02
  const hi = Math.max(0.7, ...pts.flatMap((r) => [r.xg_share, r.goal_share])) + 0.02
  const y = (v) => M.t + ((hi - v) / (hi - lo)) * (H - M.t - M.b)
  const line = (key) => pts.map((r, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(r[key]).toFixed(1)}`).join(' ')
  const ticks = [0.3, 0.4, 0.5, 0.6, 0.7].filter((t) => t >= lo && t <= hi)
  return (
    <figure style={{ margin: '0 0 12px' }}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Rolling ${window}-game expected goal share and goal share`} style={{ width: '100%', maxWidth: 720, height: 'auto' }}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} stroke="currentColor" strokeOpacity={t === 0.5 ? 0.45 : 0.15} strokeDasharray={t === 0.5 ? '' : '3 3'} />
            <text x={M.l - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="currentColor" opacity="0.7">{Math.round(t * 100)}%</text>
          </g>
        ))}
        <path d={line('xg_share')} fill="none" stroke="var(--accent, #2a6df4)" strokeWidth="2.5" />
        <path d={line('goal_share')} fill="none" stroke="currentColor" strokeOpacity="0.75" strokeWidth="2" strokeDasharray="6 4" />
        <text x={x(0)} y={H - 8} fontSize="11" fill="currentColor" opacity="0.7">{day(pts[0].date)}</text>
        <text x={x(n - 1)} y={H - 8} textAnchor="end" fontSize="11" fill="currentColor" opacity="0.7">{day(pts[n - 1].date)}</text>
      </svg>
      <figcaption className="muted">
        Last {window} games, over the games with shots stored. <strong style={{ color: 'var(--accent, #2a6df4)' }}>Solid</strong>: expected goal share (the play).
        <strong> Dashed</strong>: goal share (the results). 50% is an even game.
      </figcaption>
    </figure>
  )
}

function Picker({ onPick, current }) {
  const [teams, setTeams] = useState(null)
  useEffect(() => {
    fetch('/api/teams').then((r) => (r.ok ? r.json() : [])).then(setTeams).catch(() => setTeams([]))
  }, [])
  return (
    <label className="h2h-pick">{current ? 'Change team' : 'Pick your team'}
      <select value={current ?? ''} onChange={(e) => e.target.value && onPick(e.target.value)} disabled={!teams}>
        <option value="">{teams ? 'Choose…' : 'Loading…'}</option>
        {(teams ?? []).slice().sort((a, b) => a.name.localeCompare(b.name)).map((t) => <option key={t.abbrev} value={t.abbrev}>{t.name}</option>)}
      </select>
    </label>
  )
}

/** Your team, game by game: results next to what the shots said, a rolling trend, key players' form, and what's next. */
export default function MyTeam() {
  const { favorite, setFavorite } = useFavoriteTeam()
  const [state, setState] = useState({ abbrev: null, data: null, error: null })

  useEffect(() => {
    if (!favorite) return
    let ignore = false
    fetch(`/api/teams/${favorite}/game-log`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status === 404 ? 'Team not found' : `API returned ${r.status}`))))
      .then((data) => !ignore && setState({ abbrev: favorite, data, error: null }))
      .catch((error) => !ignore && setState({ abbrev: favorite, data: null, error: error.message }))
    return () => { ignore = true }
  }, [favorite])

  const { data, error } = state.abbrev === favorite ? state : { data: null, error: null }
  const games = useMemo(() => (data ? [...data.games].reverse() : []), [data])
  const form = useMemo(() => (data ? data.games.slice(-10) : []), [data])

  if (!favorite) {
    return (
      <main>
        <header><h1>My team</h1><p>Pick the team you follow and this page tracks its season game by game, with what the shots said next to each result.</p></header>
        <div className="h2h-picks"><Picker onPick={setFavorite} current={null} /></div>
      </main>
    )
  }
  const t = data?.team
  const s = data?.summary

  return (
    <main>
      <header className="team-head">
        {t && <TeamLogo team={t} size={56} />}
        <div>
          <h1>{t?.name ?? favorite}</h1>
          <p>
            {t && <>{t.wins}-{t.losses}-{t.ot_losses}, {t.points} points in {t.games_played} games. </>}
            <Link to={`/team/${favorite}`}>Full team page</Link>
          </p>
        </div>
      </header>
      <div className="h2h-picks"><Picker onPick={setFavorite} current={favorite} /></div>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && data.games.length === 0 && <p className="status">No finished games yet.</p>}

      {data && data.games.length > 0 && (
        <>
          <section>
            <h2>Form</h2>
            <p>
              {form.map((g) => (
                <Link key={g.game_id} to={`/game/${g.game_id}`} className={g.result === 'W' ? 'badge' : 'badge warn'} style={{ marginRight: 4 }}
                      title={`${day(g.date)} ${g.home_game ? 'vs' : '@'} ${g.opponent} ${g.gf}-${g.ga}`}>{g.result}</Link>
              ))}
              <span className="muted"> last {form.length}, oldest to newest</span>
            </p>
            {s.xg_share != null && (
              <p>
                The play: <strong>{pct(s.xg_share)}</strong> of the expected goals ({s.xgf.toFixed(1)} for, {s.xga.toFixed(1)} against) over {s.shot_games} games.
                The results: <strong>{pct(s.goal_share)}</strong> of the goals ({s.gf} for, {s.ga} against).
                {s.verdict && <> {VERDICT[s.verdict]}</>}
              </p>
            )}
            <ShareChart rolling={data.rolling} window={data.window} />
          </section>

          <section>
            <h2>Game by game</h2>
            <p className="sub">
              Newest first. xG is our own expected-goals model; xG share is the team's part of both sides' chances (50% is even). PP xG is
              what the power play created and PK xG what the other team's power play created against yours. A shootout win shows as a one-goal win.
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th className="left">Date</th><th className="left">Opponent</th><th>Result</th><th>Score</th>
                    <th title="Expected goals for">xGF</th><th title="Expected goals against">xGA</th><th title="Share of the expected goals">xG share</th>
                    <th title="Share of shot attempts">CF%</th><th title="Shots on goal for-against">SOG</th>
                    <th title="Expected goals the team's power play created">PP xG</th><th title="Expected goals against while the other team had a power play">PK xG against</th>
                  </tr>
                </thead>
                <tbody>
                  {games.map((g) => (
                    <tr key={g.game_id}>
                      <td className="left">{day(g.date)}</td>
                      <td className="left">{g.home_game ? 'vs' : '@'} <Link to={`/team/${g.opponent}`}>{g.opponent}</Link></td>
                      <td className={g.result === 'W' ? 'accent' : ''}>{g.result}{g.last_period !== 'REG' ? `/${g.last_period}` : ''}</td>
                      <td><Link to={`/game/${g.game_id}`}>{g.gf}-{g.ga}</Link></td>
                      <td>{xg(g.xgf)}</td><td>{xg(g.xga)}</td><td className="accent">{pct(g.xg_share)}</td>
                      <td>{pct(g.cf_pct)}</td><td>{g.has_shots ? `${g.sf}-${g.sa}` : '–'}</td><td>{xg(g.pp_xgf)}</td><td>{xg(g.pk_xga)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {data.players.length > 0 && (
            <section>
              <h2>Key players</h2>
              <p className="sub">The team's top scorers, with how their last {data.players[0].recent_games ?? 'few'} games compare with their season pace.</p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th className="left">Player</th><th>GP</th><th>P</th><th title="Points over a full season at the current rate">Pace</th><th title="Points in the player's recent games">Last games P</th><th title="Points over a full season at the recent rate">Last games pace</th><th /></tr>
                  </thead>
                  <tbody>
                    {data.players.map((p) => (
                      <tr key={p.player_id}>
                        <td className="left"><Link to={`/player/${p.player_id}`}>{p.name}</Link> <span className="muted">{p.position}</span></td>
                        <td>{p.games_played}</td><td>{p.points}</td><td>{fmt1(p.point_pace)}</td>
                        <td>{p.recent_points ?? '–'}</td><td>{fmt1(p.recent_pace)}</td>
                        <td>{p.form === 'hot' ? <span className="badge">hot</span> : p.form === 'cold' ? <span className="badge warn">cold</span> : null}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <Schedule abbrev={favorite} />
          <SpecialTeams abbrev={favorite} />
        </>
      )}
    </main>
  )
}
