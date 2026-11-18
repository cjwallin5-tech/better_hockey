import { useEffect, useState } from 'react'
import BackLink from '../components/BackLink.jsx'
import { useParams } from 'react-router-dom'
import PageTabs from '../components/PageTabs.jsx'
import PlayerNews from '../components/PlayerNews.jsx'
import Career from '../components/Career.jsx'
import Trophies from '../components/Trophies.jsx'
import Rankings, { rankNote, useRankings } from '../components/Rankings.jsx'
import { GoalieShots } from '../components/Shots.jsx'
import GoalieZones from '../components/GoalieZones.jsx'
import TrackingProfile from '../components/TrackingProfile.jsx'
import LuckPanel from '../components/Luck.jsx'
import GoalieProjection from '../components/GoalieProjection.jsx'
import { GoalieForm } from '../components/Form.jsx'
import CareerPlayer from './CareerPlayer.jsx'
import Context from '../components/Context.jsx'
import { GsaaChart } from '../components/Charts.jsx'
import { fmt1, fmtToi } from '../format.js'
import PlayerBanner from '../components/PlayerBanner.jsx'
import Awards from '../components/Awards.jsx'
import InternationalMedals from '../components/InternationalMedals.jsx'
import { describe } from '../glossary.js'
import PageSkeleton from '../components/Skeleton.jsx'
import { StatCards, Tile } from '../components/StatCards.jsx'
import { GOALIE_STATS, goaliePercentiles } from '../goaliePercentiles.js'
import { getJson } from '../lists.js'

const fmtSv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))
const fmt2 = (v) => (v == null ? '–' : v.toFixed(2))
const fmtSigned = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`)

export default function Goalie() {
  const { id } = useParams()
  const [result, setResult] = useState({ id: null, data: null, error: null })
  const ranks = useRankings(Number(id))
  const rank = (stat) => rankNote(ranks?.season?.[stat], 'season')
  const [leagueGoalies, setLeagueGoalies] = useState(null) // every goalie this season, for the percentile cards

  useEffect(() => {
    let ignore = false
    getJson('/api/goalies').then((d) => !ignore && setLeagueGoalies(d.goalies)).catch(() => {})
    return () => { ignore = true }
  }, [])

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
  const back = <BackLink to="/goalies" />
  if (error === 'Goalie not found') return <CareerPlayer id={Number(id)} goalie />
  if (error) return <main>{back}<p className="status">{error}</p></main>
  if (!data) return <main>{back}<PageSkeleton /></main>

  const { goalie: g, games, league_sv_pct: lg, recent_window: window } = data
  const chrono = [...games].reverse()
  const gameGsaa = (x) => (x.shots_against ?? 0) * (1 - lg) - (x.goals_against ?? 0)

  const { percentiles, peerCount, minStarts } = goaliePercentiles(g, leagueGoalies)

  return (
    <main className="player-page">
      {back}
      <PlayerBanner
        p={g}
        kind="goalie"
        stats={[
          { label: 'Save %', value: fmtSv(g.save_pct), rank: rank('save_pct'), big: true },
          { label: 'GAA', value: fmt2(g.gaa), rank: rank('gaa'), big: true },
          { label: 'GSAA', value: fmtSigned(g.gsaa), big: true },
          { label: 'W-L-OTL', value: `${g.wins}-${g.losses}-${g.ot_losses}`, rank: rank('wins'), big: true },
          { label: 'GP / GS', value: `${g.games_played} / ${g.games_started}` },
          { label: 'Shutouts', value: g.shutouts, rank: rank('shutouts') },
          { label: `Last ${g.recent_games ?? 0} SV%`, value: fmtSv(g.recent_save_pct) },
          { label: `Last ${g.recent_games ?? 0} GSAA`, value: fmtSigned(g.recent_gsaa) },
        ]}
      />

      <PageTabs
        tabs={[
          {
            id: 'stats',
            label: 'Stats',
            content: (
              <>
                <Context playerId={g.player_id} goalie />
                <div className="player-overview">
                  <section className="explain">
                    <h2>Season performance</h2>
                    <p className="sub">
                      Percentile among {peerCount || '–'} goalies with at least {minStarts || '–'} starts. League-average save % is {fmtSv(lg)}.
                      Recent form covers the last {window} appearances.
                    </p>
                    <StatCards stats={GOALIE_STATS} p={g} percentiles={percentiles} />
                  </section>
                  <aside>
                    <GoalieProjection playerId={g.player_id} />
                  </aside>
                </div>
                <Rankings playerId={g.player_id} kind="goalie" />
                <Career playerId={g.player_id} />
                <Trophies playerId={g.player_id} />
                <Awards playerId={g.player_id} />
                <InternationalMedals playerId={g.player_id} />
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
                      <th className="left">Date</th><th className="left">Opponent</th><th title={describe('Start')}>Start</th>
                      <th title={describe('Dec')}>Dec</th><th title={describe('SA')}>SA</th><th title={describe('SV')}>SV</th><th title={describe('GA')}>GA</th><th title={describe('SV%')}>SV%</th><th title={describe('GSAA')}>GSAA</th><th title={describe('TOI')}>TOI</th>
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
          {
            id: 'advanced',
            label: 'Advanced',
            content: (
              <PageTabs
                param="view"
                pills
                tabs={[
                  { id: 'profile', label: 'Profile', content: <TrackingProfile playerId={g.player_id} /> },
                  {
                    id: 'workload',
                    label: 'Workload & usage',
                    content: (
                      <>
                        <h2>Workload</h2>
                        <p className="sub">How often he plays and how much he faces. Goal support is how many goals his team scores for him.</p>
                        <section className="tiles tiles-sm">
                          <Tile label="Games started" value={`${g.games_started ?? '–'} of ${g.games_played ?? '–'}`} />
                          <Tile label="Quality starts" value={`${g.quality_starts ?? '–'} (${fmtSv(g.quality_start_pct)})`} />
                          <Tile label="GSAA / 60" value={fmtSigned(g.gsaa_per60)} />
                          <Tile label="Shots against / 60" value={fmt1(g.shots_against_per60)} />
                          <Tile label="Goal support / game" value={fmt2(g.goal_support_avg)} />
                          <Tile label="Time on ice" value={fmtToi(g.toi_sec)} />
                        </section>
                        <h2>Save % by situation</h2>
                        <div className="splits">
                          <Split label="Even strength" saves={g.ev_saves} shots={g.ev_shots_against} pct={g.ev_save_pct} />
                          <Split label="Penalty kill" saves={g.pp_saves} shots={g.pp_shots_against} pct={g.pp_save_pct} />
                          <Split label="Power play (short-handed shots)" saves={g.sh_saves} shots={g.sh_shots_against} pct={g.sh_save_pct} />
                        </div>
                      </>
                    ),
                  },
                  { id: 'shots', label: 'Shots faced', content: <GoalieShots playerId={g.player_id} /> },
                  { id: 'zones', label: 'Weak spots', content: <GoalieZones playerId={g.player_id} /> },
                  { id: 'luck', label: 'Luck', content: <LuckPanel playerId={g.player_id} goalie /> },
                ]}
              />
            ),
          },
          {
            id: 'trends',
            label: 'Trends',
            content: (
              <>
              <GoalieForm games={chrono} leagueSvPct={lg} />

              <div className="charts">
                <GsaaChart games={chrono} leagueSvPct={lg} />
              </div>
              </>
            ),
          },
          { id: 'news', label: 'News', content: <PlayerNews playerId={g.player_id} name={g.name} team={g.team} /> },
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
