import { useEffect, useState } from 'react'
import BackLink from '../components/BackLink.jsx'
import { Link, useParams } from 'react-router-dom'
import ShotMap from '../components/ShotMap.jsx'
import { CorsiFlow, ShiftChart, WinProbability, XgFlow } from '../components/GameCharts.jsx'
import { fmtPct, fmtToi } from '../format.js'
import { describe } from '../glossary.js'
import GameLines from '../components/GameLines.jsx'
import PageSkeleton from '../components/Skeleton.jsx'
import PageTabs from '../components/PageTabs.jsx'
import GameBanner from '../components/GameBanner.jsx'
import GameVersus from '../components/GameVersus.jsx'
import TeamMark from '../components/TeamMark.jsx'

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
  const [playersSideState, setPlayersSide] = useState(null)

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
  const back = <BackLink to="/" />
  if (error) return <main>{back}<p className="status">{error}</p></main>
  if (!data) return <main>{back}<PageSkeleton /></main>

  const { game: g, teams, goals, skaters, goalies, shots, win_probability: wp, lines = [], pairs = [] } = data
  const finished = g.state === 'OFF' || g.state === 'FINAL'
  const sides = [g.away, g.home]
  const score = { [g.away]: g.away_score, [g.home]: g.home_score }
  const hasShots = shots.length > 0
  const side = mapSide ?? g.away
  const playersSide = playersSideState ?? g.away


  return (
    <main>
      {back}
      <GameBanner g={g} score={score} finished={finished} goals={goals} teams={teams} hasShots={hasShots} />

      <PageTabs
        tabs={[
          {
            id: 'summary',
            label: 'Summary',
            content: (
              <>
      {goals.length > 0 && (
        <>
          <h2>Scoring</h2>
          <ul className="goal-list">
            {goals.map((x, i) => (
              <li key={i}>
                <span className="muted">{goalClock(x.time_sec)}</span>
                <span className="goal-team"><TeamMark abbrev={x.team} size={22} /> {x.team}</span>
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
      <GameVersus
        away={g.away}
        home={g.home}
        rows={[
          ...(hasShots ? [
            ['Shots on goal', teams[g.away].on_goal, teams[g.home].on_goal],
            ['Shot attempts', teams[g.away].attempts, teams[g.home].attempts],
            ['Expected goals (xG)', teams[g.away].xg, teams[g.home].xg, (v) => v.toFixed(2)],
          ] : []),
          ['Hits', teams[g.away].hits, teams[g.home].hits],
          ['Blocked shots', teams[g.away].blocks, teams[g.home].blocks],
          ['Takeaways', teams[g.away].takeaways, teams[g.home].takeaways],
          ['Giveaways', teams[g.away].giveaways, teams[g.home].giveaways],
          ['Penalty minutes', teams[g.away].pim, teams[g.home].pim],
        ]}
      />
              </>
            ),
          },
          {
            id: 'players',
            label: 'Players',
            content: (
              <>
                <div className="subtabs" role="tablist">
                  {sides.map((s) => (
                    <button key={s} role="tab" aria-selected={playersSide === s} className={playersSide === s ? 'on' : ''} onClick={() => setPlayersSide(s)}>{s}</button>
                  ))}
                </div>
      {sides.filter((t) => t === playersSide).map((team) => (
        <section key={team}>
          <h2>{team} skaters</h2>
          <div className="table-wrap fit">
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
          <div className="table-wrap fit" style={{ marginTop: 8 }}>
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

              </>
            ),
          },
          { id: 'lines', label: 'Lines', content: (
      <GameLines lines={lines} pairs={pairs} sides={sides} />
          ) },
          {
            id: 'charts',
            label: 'Charts',
            content: (
              <>
      {hasShots && <XgFlow shots={shots} goals={goals} away={g.away} home={g.home} />}

      {hasShots && <CorsiFlow shots={shots} goals={goals} away={g.away} home={g.home} />}

      {finished && <ShiftChart game={g} goals={goals} away={g.away} home={g.home} />}

              </>
            ),
          },
          ...(hasShots ? [{
            id: 'shots',
            label: 'Shot map',
            content: (
        <section>
          <h2>Shot map</h2>
          <div className="subtabs" role="tablist">
            {sides.map((s) => (
              <button key={s} role="tab" aria-selected={side === s} className={side === s ? 'on' : ''} onClick={() => setMapSide(s)}>{s} shots</button>
            ))}
          </div>
          <ShotMap key={side} shots={shots.filter((s) => s.team === side)} caption={`${side} shots`} />
        </section>
            ),
          }] : []),
        ]}
      />
    </main>
  )
}
