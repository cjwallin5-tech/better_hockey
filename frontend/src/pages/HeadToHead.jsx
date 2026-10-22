import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { seasonLabel } from '../career.js'
import { describe } from '../glossary.js'

const day = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
const RESULT = { W: 'W', OTW: 'W (OT/SO)', OTL: 'L (OT/SO)', L: 'L' }
const fixed = (v, d = 2) => (v == null ? '–' : v.toFixed(d))

function useFetch(url) {
  const [state, setState] = useState({ url: null, data: null, error: null })
  useEffect(() => {
    if (!url) return undefined
    let ignore = false
    fetch(url)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `API returned ${r.status}`)
        return r.json()
      })
      .then((data) => !ignore && setState({ url, data, error: null }))
      .catch((error) => !ignore && setState({ url, data: null, error: error.message }))
    return () => { ignore = true }
  }, [url])
  return state.url === url ? state : { data: null, error: null }
}

function TeamSelect({ label, value, onChange, teams, exclude }) {
  return (
    <label className="h2h-pick">{label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Choose a team…</option>
        {teams.filter((t) => t.abbrev !== exclude).map((t) => <option key={t.abbrev} value={t.abbrev}>{t.name}</option>)}
      </select>
    </label>
  )
}

function TeamVsTeam({ teams, a, b, setA, setB }) {
  const { data, error } = useFetch(a && b && a !== b ? `/api/head-to-head/teams?a=${a}&b=${b}` : null)
  const s = data?.summary
  return (
    <>
      <div className="h2h-picks">
        <TeamSelect label="Team" value={a} onChange={setA} teams={teams} exclude={b} />
        <span className="muted">vs</span>
        <TeamSelect label="Opponent" value={b} onChange={setB} teams={teams} exclude={a} />
      </div>
      {!a || !b ? <p className="status">Pick two teams to see how their games have gone.</p> : null}
      {error && <p className="status">{error}</p>}
      {data && s.games === 0 && <p className="status">These teams haven't met in the games we store.</p>}
      {data && s.games > 0 && (
        <>
          <section className="tiles">
            <div className="tile"><span>Record</span><strong>{data.a.abbrev} {s.a_wins}–{s.b_wins} {data.b.abbrev}</strong></div>
            <div className="tile"><span>Goals</span><strong>{s.a_goals}–{s.b_goals}</strong></div>
            <div className="tile"><span>Games</span><strong>{s.games}</strong></div>
            <div className="tile"><span>Streak</span><strong>{s.streak ? `${s.streak.team === 'a' ? data.a.abbrev : data.b.abbrev} ${s.streak.games}` : '–'}</strong></div>
          </section>
          <p className="sub">
            Since {seasonLabel(data.first_season)}: {data.a.name} {s.a_wins}–{s.b_wins} against the {data.b.name} ({s.a_ot_losses + s.b_ot_losses} games
            went past regulation: {data.a.abbrev} lost {s.a_ot_losses}, {data.b.abbrev} lost {s.b_ot_losses}).
          </p>
          <h2>By season</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Season</th><th title={describe('GP')}>GP</th><th>{data.a.abbrev} W</th><th>{data.b.abbrev} W</th><th>Goals</th></tr></thead>
              <tbody>
                {s.by_season.map((x) => (
                  <tr key={x.season_id}>
                    <td className="left">{seasonLabel(x.season_id)}</td><td>{x.games}</td><td>{x.a_wins}</td><td>{x.b_wins}</td><td>{x.gf}–{x.ga}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h2>Recent meetings</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Date</th><th>Score ({data.a.abbrev}–{data.b.abbrev})</th><th>Result for {data.a.abbrev}</th></tr></thead>
              <tbody>
                {data.recent.map((g) => (
                  <tr key={g.game_id}>
                    <td className="left">{g.link ? <Link to={`/game/${g.game_id}`}>{day(g.game_date)}</Link> : day(g.game_date)}</td>
                    <td>{g.gf}–{g.ga}</td>
                    <td className={g.result === 'W' || g.result === 'OTW' ? 'accent' : ''}>{RESULT[g.result]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}

function PlayerVsTeam({ teams, playerId, team, setPlayer, setTeam, goalie = false }) {
  const [query, setQuery] = useState('')
  const [found, setFound] = useState({ q: '', rows: [] })
  const { data, error } = useFetch(playerId && team ? `/api/head-to-head/${goalie ? 'goalie' : 'player'}?player_id=${playerId}&team=${team}` : null)

  useEffect(() => {
    const q = query.trim()
    if (!q) return undefined
    const ctl = new AbortController()
    const t = setTimeout(() => {
      fetch(`/api/alltime/${goalie ? 'goalie' : 'skater'}?q=${encodeURIComponent(q)}&limit=8`, { signal: ctl.signal })
        .then((r) => r.json())
        .then((d) => setFound({ q, rows: d.rows ?? [] }))
        .catch(() => {})
    }, 200)
    return () => { clearTimeout(t); ctl.abort() }
  }, [query, goalie])
  const matches = query.trim() && found.q === query.trim() ? found.rows : []
  const vs = data?.vs, rest = data?.rest
  const svp = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))

  return (
    <>
      <div className="h2h-picks">
        <label className="h2h-pick">{goalie ? 'Goalie' : 'Player'}
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={data ? data.player.name : `Search for a ${goalie ? 'goalie' : 'skater'}…`} />
        </label>
        <span className="muted">vs</span>
        <TeamSelect label="Team" value={team} onChange={setTeam} teams={teams} />
      </div>
      {matches.length > 0 && (
        <ul className="h2h-matches">
          {matches.map((m) => (
            <li key={m.player_id}>
              <button type="button" className="link-button" onClick={() => { setPlayer(String(m.player_id)); setQuery('') }}>
                {m.name} <span className="muted">{goalie ? 'G' : m.position}{m.first_season ? ` · debut ${String(m.first_season).slice(0, 4)}` : ''}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {!playerId || !team ? <p className="status">Search for a {goalie ? 'goalie' : 'skater'} and pick a team to see how {goalie ? 'they have played' : 'they score'} against them.</p> : null}
      {error && <p className="status">{error}</p>}
      {data && vs.games === 0 && (
        <p className="status">
          {data.player.name} has no stored games against {data.team.name}. We keep game-by-game lines for this season and the
          previous four, so older or retired players may have none.
        </p>
      )}
      {data && vs.games > 0 && goalie && (
        <>
          <h2><Link to={`/goalie/${data.player.player_id}`}>{data.player.name}</Link> vs. {data.team.name}</h2>
          <section className="tiles">
            <div className="tile"><span>Games</span><strong>{vs.games}</strong></div>
            <div className="tile"><span>SV%</span><strong>{svp(vs.save_pct)}</strong></div>
            <div className="tile"><span>Goals against / game</span><strong>{fixed(vs.goals_against_per_game)}</strong></div>
            <div className="tile"><span>SV% vs. everyone else</span><strong>{svp(rest.save_pct)}</strong></div>
          </section>
          <p className="sub">
            Over {data.stored_games} stored games, {data.player.name} stopped {svp(vs.save_pct)} of shots against {data.team.abbrev} and{' '}
            {svp(rest.save_pct)} against everyone else. {vs.shots_against < 400 ? `Only ${vs.shots_against} shots were faced, so a gap here is more likely noise than a matchup effect.` : ''}{' '}
            Past seasons are rebuilt from stored shots, so a game with no usable shot data is missing.
          </p>
          <h2>By season</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Season</th><th title={describe('GP')}>GP</th><th>SA</th><th>GA</th><th title={describe('SV%')}>SV%</th></tr></thead>
              <tbody>
                {data.by_season.map((x) => (
                  <tr key={x.season_id}><td className="left">{seasonLabel(x.season_id)}</td><td>{x.games}</td><td>{x.shots_against}</td><td>{x.goals_against}</td><td>{svp(x.save_pct)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <h2>Recent games</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Date</th><th>SA</th><th>GA</th><th title={describe('SV%')}>SV%</th></tr></thead>
              <tbody>
                {data.recent.map((g) => (
                  <tr key={g.game_id}><td className="left">{day(g.game_date)}</td><td>{g.shots_against}</td><td>{g.goals_against}</td><td>{svp(g.shots_against ? (g.shots_against - g.goals_against) / g.shots_against : null)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {data && vs.games > 0 && !goalie && (
        <>
          <h2><Link to={`/player/${data.player.player_id}`}>{data.player.name}</Link> vs. {data.team.name}</h2>
          <section className="tiles">
            <div className="tile"><span>Games</span><strong>{vs.games}</strong></div>
            <div className="tile"><span>G–A–P</span><strong>{vs.goals}–{vs.assists}–{vs.points}</strong></div>
            <div className="tile"><span>Points / game</span><strong>{fixed(vs.points_per_game)}</strong></div>
            <div className="tile"><span>vs. everyone else</span><strong>{fixed(rest.points_per_game)}</strong></div>
          </section>
          <p className="sub">
            Over {data.stored_games} stored games, {data.player.name} scored {fixed(vs.points_per_game)} points per game against {data.team.abbrev} and{' '}
            {fixed(rest.points_per_game)} against everyone else. {vs.games < 15 ? `A sample of ${vs.games} games is small, so a gap here is more likely noise than a matchup effect.` : ''}
          </p>
          <h2>By season</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Season</th><th title={describe('GP')}>GP</th><th title={describe('G')}>G</th><th title={describe('A')}>A</th><th title={describe('P')}>P</th><th title={describe('P/GP')}>P/GP</th></tr></thead>
              <tbody>
                {data.by_season.map((x) => (
                  <tr key={x.season_id}><td className="left">{seasonLabel(x.season_id)}</td><td>{x.games}</td><td>{x.goals}</td><td>{x.assists}</td><td>{x.points}</td><td>{fixed(x.points_per_game)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <h2>Recent games</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Date</th><th title={describe('G')}>G</th><th title={describe('A')}>A</th><th title={describe('P')}>P</th></tr></thead>
              <tbody>
                {data.recent.map((g) => (
                  <tr key={g.game_id}><td className="left">{day(g.game_date)}</td><td>{g.goals}</td><td>{g.assists}</td><td>{g.goals + g.assists}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}

export default function HeadToHead() {
  const [params, setParams] = useSearchParams()
  const mode = ['player', 'goalie'].includes(params.get('mode')) ? params.get('mode') : 'team'
  const [teams, setTeams] = useState([])
  useEffect(() => {
    fetch('/api/teams').then((r) => r.json()).then((rows) => setTeams([...rows].sort((x, y) => x.name.localeCompare(y.name)))).catch(() => {})
  }, [])

  const update = (patch) => {
    const next = new URLSearchParams(params)
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v)
      else next.delete(k)
    }
    setParams(next, { replace: true })
  }

  return (
    <main>
      <header>
        <h1>Head-to-head</h1>
        <p>
          How teams, skaters and goalies have done against each other. Covers this season and the previous four; the
          Coyotes' games count toward Utah.
        </p>
      </header>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={mode === 'team'} className={mode === 'team' ? 'on' : ''} onClick={() => update({ mode: '', p: '' })}>Team vs. team</button>
        <button role="tab" aria-selected={mode === 'player'} className={mode === 'player' ? 'on' : ''} onClick={() => update({ mode: 'player', p: '' })}>Skater vs. team</button>
        <button role="tab" aria-selected={mode === 'goalie'} className={mode === 'goalie' ? 'on' : ''} onClick={() => update({ mode: 'goalie', p: '' })}>Goalie vs. team</button>
      </div>
      {mode === 'team' ? (
        <TeamVsTeam teams={teams} a={params.get('a') ?? ''} b={params.get('b') ?? ''} setA={(v) => update({ a: v })} setB={(v) => update({ b: v })} />
      ) : (
        <PlayerVsTeam key={mode} goalie={mode === 'goalie'} teams={teams} playerId={params.get('p') ?? ''} team={params.get('t') ?? ''} setPlayer={(v) => update({ p: v })} setTeam={(v) => update({ t: v })} />
      )}
    </main>
  )
}
