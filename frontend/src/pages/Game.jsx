import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import ShotMap from '../components/ShotMap.jsx'
import { CorsiFlow, ShiftChart, WinProbability, XgFlow } from '../components/GameCharts.jsx'
import { fmtPct, fmtToi } from '../format.js'
import { describe } from '../glossary.js'
import GameLines from '../components/GameLines.jsx'

const longDate = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
const mmss = (sec) => `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`
const goalClock = (sec) => {
  const period = Math.min(Math.floor((sec - 1) / 1200) + 1, 4)
  const into = ((sec - 1) % 1200) + 1
  return `${period === 4 ? 'OT' : `P${period}`} ${mmss(into)}`
}
const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))

export default function Game() {
  const { id } = useParams()
  const [result, setResult] = useState({ id: null, data: null, error: null })
  const [mapSide, setMapSide] = useState(null)

  useEffect(() => {
    fetch(`/api/games/${id}`)
      .then((r) => {
        if (r.status === 404) throw new Error('Game not found')
        if (!r.ok) throw new Error(`API returned ${r.status}`)
        return r.json()
      })
      .then((data) => setResult({ id, data, error: null }))
      .catch((error) => setResult({ id, data: null, error: error.message }))
  }, [id])

  const { data, error } = result.id === id ? result : { data: null, error: null }
  const back = <Link to="/" className="back">← Home</Link>
  if (error) return <main>{back}<p className="status">{error}</p></main>
  if (!data) return <main>{back}<p className="status">Loading…</p></main>

  const { game: g, teams, goals, skaters, goalies, shots, win_probability: wp, lines = [], pairs = [] } = data
  const finished = g.state === 'OFF' || g.state === 'FINAL'
  const sides = [g.away, g.home]
  const score = { [g.away]: g.away_score, [g.home]: g.home_score }
  const hasShots = shots.length > 0
  const side = mapSide ?? g.away

  const compare = [
    ['Shots on goal', (t) => t.on_goal, hasShots],
    ['Shot attempts', (t) => t.attempts, hasShots],
    ['Expected goals (xG)', (t) => t.xg.toFixed(2), hasShots],
    ['Hits', (t) => t.hits, true],
    ['Blocked shots', (t) => t.blocks, true],
    ['Takeaways', (t) => t.takeaways, true],
    ['Giveaways', (t) => t.giveaways, true],
    ['Penalty minutes', (t) => t.pim, true],
  ].filter((r) => r[2])

  return (
    <main>
      {back}
      <header className="game-head">
        <div className="game-score">
          {sides.map((s, i) => (
            <span key={s} className={finished && score[s] > score[sides[1 - i]] ? 'win' : ''}>
              <Link to={`/team/${s}`}>{s}</Link> <strong>{score[s] ?? '–'}</strong>
            </span>
          ))}
        </div>
        <p>
          {finished ? (g.last_period === 'REG' ? 'Final' : `Final / ${g.last_period}`) : g.state} · {longDate(g.game_date)}
          {g.venue ? ` · ${g.venue}` : ''}
          {' · '}<Link to={`/head-to-head?a=${g.home}&b=${g.away}`}>Head-to-head history</Link>
        </p>
      </header>

      {goals.length > 0 && (
        <>
          <h2>Scoring</h2>
          <ul className="goal-list">
            {goals.map((x, i) => (
              <li key={i}>
                <span className="muted">{goalClock(x.time_sec)}</span>
                <strong>{x.team}</strong>
                <span><Link to={`/player/${x.shooter_id}`}>{x.scorer}</Link>
                  <span className="muted">{x.shot_type ? ` · ${x.shot_type}` : ''}{x.strength && x.strength !== 'ev' ? ` · ${x.strength.toUpperCase()}` : ''}{x.xg != null ? ` · ${(x.xg * 100).toFixed(0)}% xG` : ''}</span>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      {wp && (
        <>
          <h2>How the game was won</h2>
          <p>{wp.story.join(' ')}</p>
          <WinProbability wp={wp} goals={goals} away={g.away} home={g.home} />
        </>
      )}

      <h2>Team comparison</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th className="left" /><th>{g.away}</th><th>{g.home}</th></tr></thead>
          <tbody>
            {compare.map(([label, get]) => (
              <tr key={label}><td className="left">{label}</td><td>{get(teams[g.away])}</td><td>{get(teams[g.home])}</td></tr>
            ))}
          </tbody>
        </table>
      </div>

      {hasShots && <XgFlow shots={shots} goals={goals} away={g.away} home={g.home} />}

      {hasShots && <CorsiFlow shots={shots} goals={goals} away={g.away} home={g.home} />}

      {finished && <ShiftChart game={g} goals={goals} away={g.away} home={g.home} />}

      {sides.map((team) => (
        <section key={team}>
          <h2>{team} skaters</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="left">Player</th><th className="left" title={describe('Pos')}>Pos</th><th title={describe('G')}>G</th><th title={describe('A')}>A</th><th title={describe('P')}>P</th><th title={describe('+/-')}>+/-</th>
                  <th title={describe('SOG')}>SOG</th><th title={describe('TOI')}>TOI</th><th title={describe('Hits')}>Hits</th><th title={describe('BLK')}>BLK</th><th title={describe('TK')}>TK</th><th title={describe('GV')}>GV</th>{hasShots && <><th title={describe('CF%')}>CF%</th><th title={describe('xGF%')}>xGF%</th></>}
                </tr>
              </thead>
              <tbody>
                {skaters.filter((p) => p.team === team).map((p) => {
                  const cfPct = p.cf != null && p.cf + p.ca > 0 ? p.cf / (p.cf + p.ca) : null
                  const xgfPct = p.xgf != null && p.xgf + p.xga > 0 ? p.xgf / (p.xgf + p.xga) : null
                  return (
                    <tr key={p.player_id}>
                      <td className="left"><Link to={`/player/${p.player_id}`}>{p.name}</Link></td>
                      <td className="left">{p.position}</td>
                      <td>{p.goals}</td><td>{p.assists}</td><td>{p.points}</td><td>{p.plus_minus ?? '–'}</td>
                      <td>{p.shots ?? '–'}</td><td>{fmtToi(p.toi_sec)}</td><td>{p.hits ?? '–'}</td><td>{p.blocked_shots ?? '–'}</td>
                      <td>{p.takeaways ?? '–'}</td><td>{p.giveaways ?? '–'}</td>
                      {hasShots && <><td>{fmtPct(cfPct)}</td><td>{fmtPct(xgfPct)}</td></>}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="table-wrap" style={{ marginTop: 8 }}>
            <table>
              <thead><tr><th className="left">Goalie</th><th title={describe('Dec')}>Dec</th><th title={describe('SA')}>SA</th><th title={describe('SV')}>SV</th><th title={describe('GA')}>GA</th><th title={describe('SV%')}>SV%</th><th title={describe('TOI')}>TOI</th></tr></thead>
              <tbody>
                {goalies.filter((x) => x.team === team).map((x) => (
                  <tr key={x.player_id}>
                    <td className="left"><Link to={`/goalie/${x.player_id}`}>{x.name}</Link>{x.started ? '' : <span className="muted"> (relief)</span>}</td>
                    <td>{x.decision ?? '–'}</td><td>{x.shots_against}</td><td>{x.saves}</td><td>{x.goals_against}</td>
                    <td>{x.shots_against ? sv(x.saves / x.shots_against) : '–'}</td><td>{mmss(x.toi_sec)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      <GameLines lines={lines} pairs={pairs} sides={sides} />

      {hasShots && (
        <section>
          <h2>Shot map</h2>
          <div className="tabs" role="tablist">
            {sides.map((s) => (
              <button key={s} role="tab" aria-selected={side === s} className={side === s ? 'on' : ''} onClick={() => setMapSide(s)}>{s} shots</button>
            ))}
          </div>
          <ShotMap key={side} shots={shots.filter((s) => s.team === side)} caption={`${side} shots`} />
        </section>
      )}
    </main>
  )
}
