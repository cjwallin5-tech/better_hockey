import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import PageTabs from '../components/PageTabs.jsx'
import Career from '../components/Career.jsx'
import Trophies from '../components/Trophies.jsx'
import Rankings from '../components/Rankings.jsx'
import FantasyStar from '../components/FantasyStar.jsx'
import { GoalieShots } from '../components/Shots.jsx'
import TrackingProfile from '../components/TrackingProfile.jsx'
import LuckPanel from '../components/Luck.jsx'
import { GoalieForm } from '../components/Form.jsx'
import CareerPlayer from './CareerPlayer.jsx'
import Context from '../components/Context.jsx'
import { GsaaChart } from '../components/Charts.jsx'
import { fmt1, fmtToi } from '../format.js'

const fmtSv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))
const fmt2 = (v) => (v == null ? '–' : v.toFixed(2))
const fmtSigned = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`)

export default function Goalie() {
  const { id } = useParams()
  const [result, setResult] = useState({ id: null, data: null, error: null })

  useEffect(() => {
    fetch(`/api/goalies/${id}`)
      .then((r) => {
        if (r.status === 404) throw new Error('Goalie not found')
        if (!r.ok) throw new Error(`API returned ${r.status}`)
        return r.json()
      })
      .then((data) => setResult({ id, data, error: null }))
      .catch((error) => setResult({ id, data: null, error: error.message }))
  }, [id])

  const { data, error } = result.id === id ? result : { data: null, error: null }
  const back = <Link to="/goalies" className="back">← All goalies</Link>
  if (error === 'Goalie not found') return <CareerPlayer id={Number(id)} goalie />
  if (error) return <main>{back}<p className="status">{error}</p></main>
  if (!data) return <main>{back}<p className="status">Loading…</p></main>

  const { goalie: g, games, league_sv_pct: lg, recent_window: window } = data
  const chrono = [...games].reverse()
  const gameGsaa = (x) => (x.shots_against ?? 0) * (1 - lg) - (x.goals_against ?? 0)

  return (
    <main>
      {back}
      <header>
        <h1>
          {g.name}{' '}
          <span>
            {g.team?.split(',').map((abbr, i) => (
              <span key={abbr}>{i > 0 && ', '}<Link to={`/team/${abbr}`}>{abbr}</Link></span>
            ))}{' '}
            · G · catches {g.catches}
          </span>
        </h1>
        <p className="header-actions">
          <FantasyStar player={{ id: g.player_id, kind: 'goalie', name: g.name }} />
          <Link to={`/compare?ids=${g.player_id}`}>Compare with other goalies →</Link>
        </p>
      </header>

      <Context playerId={g.player_id} goalie />
      <Trophies playerId={g.player_id} />

      <section className="tiles">
        <Tile label="GP / GS" value={`${g.games_played} / ${g.games_started}`} />
        <Tile label="W-L-OTL" value={`${g.wins}-${g.losses}-${g.ot_losses}`} />
        <Tile label="Save %" value={fmtSv(g.save_pct)} />
        <Tile label="GAA" value={fmt2(g.gaa)} />
        <Tile label="GSAA" value={fmtSigned(g.gsaa)} />
        <Tile label="GSAA / 60" value={fmtSigned(g.gsaa_per60)} />
        <Tile label="Quality starts" value={`${g.quality_starts ?? '–'} (${fmtSv(g.quality_start_pct)})`} />
        <Tile label="Shots against / 60" value={fmt1(g.shots_against_per60)} />
        <Tile label="Goal support / game" value={fmt2(g.goal_support_avg)} />
        <Tile label="Shutouts" value={g.shutouts} />
        <Tile label={`Last ${g.recent_games ?? 0} SV%`} value={fmtSv(g.recent_save_pct)} />
        <Tile label={`Last ${g.recent_games ?? 0} GSAA`} value={fmtSigned(g.recent_gsaa)} />
      </section>
      <p className="sub">
        League-average save % is {fmtSv(lg)}. Recent form covers the last {window} appearances.
      </p>

      <PageTabs
        tabs={[
          {
            id: 'season',
            label: 'This season',
            content: (
              <>
              <GoalieForm games={chrono} leagueSvPct={lg} />

              <div className="charts">
                <GsaaChart games={chrono} leagueSvPct={lg} />
                <figure className="chart">
                  <figcaption><h3>Save % by situation</h3></figcaption>
                  <div className="splits">
                    <Split label="Even strength" saves={g.ev_saves} shots={g.ev_shots_against} pct={g.ev_save_pct} />
                    <Split label="Penalty kill" saves={g.pp_saves} shots={g.pp_shots_against} pct={g.pp_save_pct} />
                    <Split label="Power play (short-handed shots)" saves={g.sh_saves} shots={g.sh_shots_against} pct={g.sh_save_pct} />
                  </div>
                </figure>
              </div>
              </>
            ),
          },
          {
            id: 'career',
            label: 'Career & rankings',
            content: (
              <>
                <Career playerId={g.player_id} />
                <Rankings playerId={g.player_id} kind="goalie" />
              </>
            ),
          },
          {
            id: 'shots',
            label: 'Shots faced',
            content: (
              <>
              <LuckPanel playerId={g.player_id} goalie />

              <TrackingProfile playerId={g.player_id} />

              <GoalieShots playerId={g.player_id} />
              </>
            ),
          },
          {
            id: 'log',
            label: 'Game log',
            content: (
              <>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th className="left">Date</th><th className="left">Opponent</th><th>Start</th>
                      <th>Dec</th><th>SA</th><th>SV</th><th>GA</th><th>SV%</th><th>GSAA</th><th>TOI</th>
                    </tr>
                  </thead>
                  <tbody>
                    {games.map((x) => (
                      <tr key={x.game_id}>
                        <td className="left">{x.game_date}</td>
                        <td className="left">{x.is_home ? 'vs' : '@'} {x.opponent}</td>
                        <td>{x.started ? 'Yes' : 'Relief'}</td>
                        <td>{x.decision ?? '–'}</td>
                        <td>{x.shots_against}</td><td>{x.saves}</td><td>{x.goals_against}</td>
                        <td>{x.shots_against ? fmtSv(x.saves / x.shots_against) : '–'}</td>
                        <td>{fmtSigned(gameGsaa(x))}</td>
                        <td>{fmtToi(x.toi_sec)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              </>
            ),
          },
        ]}
      />
    </main>
  )
}

// A save-percentage bar with a marker at the league-average line is overkill for three rows;
// the number, the shot count and a proportional bar tell the story.
function Split({ label, saves, shots, pct }) {
  return (
    <div className="split">
      <div className="def-top">
        <span>{label}</span>
        <strong>{fmtSv(pct)}</strong>
      </div>
      <div className="bar"><div style={{ width: `${(pct ?? 0) * 100}%` }} /></div>
      <div className="def-foot">{saves ?? '–'} saves on {shots ?? '–'} shots</div>
    </div>
  )
}

function Tile({ label, value }) {
  return (
    <div className="tile">
      <span>{label}</span>
      <strong>{value ?? '–'}</strong>
    </div>
  )
}
