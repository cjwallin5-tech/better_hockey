import { useEffect, useState } from 'react'
import PenaltyKill from '../components/PenaltyKill.jsx'
import BackLink from '../components/BackLink.jsx'
import { useParams } from 'react-router-dom'
import PageTabs from '../components/PageTabs.jsx'
import PlayerNews from '../components/PlayerNews.jsx'
import Career from '../components/Career.jsx'
import Trophies from '../components/Trophies.jsx'
import Rankings, { rankNote, useRankings } from '../components/Rankings.jsx'
import CareerPlayer from './CareerPlayer.jsx'
import Context from '../components/Context.jsx'
import { Linemates } from '../components/Lines.jsx'
import { SkaterShots } from '../components/Shots.jsx'
import PaceHistory from '../components/PaceHistory.jsx'
import Similar from '../components/Similar.jsx'
import ScoutingCard from '../components/ScoutingCard.jsx'
import Comparables from '../components/Comparables.jsx'
import DefenseProfile from '../components/DefenseProfile.jsx'
import TrackingProfile from '../components/TrackingProfile.jsx'
import LuckPanel from '../components/Luck.jsx'
import Projection from '../components/Projection.jsx'
import Explain from '../components/Explain.jsx'
import ScoreState from '../components/ScoreState.jsx'
import ShooterZones from '../components/ShooterZones.jsx'
import { SkaterForm } from '../components/Form.jsx'
import { RolePanel } from '../components/Roles.jsx'
import { CorsiChart, DefenseBars, GameBars, PaceChart } from '../components/Charts.jsx'
import PlayerBanner from '../components/PlayerBanner.jsx'
import Awards from '../components/Awards.jsx'
import InternationalMedals from '../components/InternationalMedals.jsx'
import { describe } from '../glossary.js'
import PossessionGuide from '../components/PossessionGuide.jsx'
import PageSkeleton from '../components/Skeleton.jsx'

const fmt1 = (v) => (v == null ? '–' : v.toFixed(1))
const fmtToi = (sec) =>
  sec == null ? '–' : `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, '0')}`

const DEFENSIVE = [
  { key: 'hits_per60', label: 'Hits / 60', fmt: fmt1 },
  { key: 'blocks_per60', label: 'Blocked shots / 60', fmt: fmt1 },
  { key: 'takeaways_per60', label: 'Takeaways / 60', fmt: fmt1 },
  { key: 'giveaways_per60', label: 'Giveaways / 60', fmt: fmt1, note: 'lower is better' },
  { key: 'hits', label: 'Hits' },
  { key: 'blocked_shots', label: 'Blocked shots' },
  { key: 'takeaways', label: 'Takeaways' },
  { key: 'giveaways', label: 'Giveaways', note: 'lower is better' },
]

const fmtPct = (v) => (v == null ? '–' : (v * 100).toFixed(1))
const fmtSignedPct = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${(v * 100).toFixed(1)}`)

const POSSESSION = [
  { key: 'sat_pct', label: 'Corsi % (CF%)', fmt: fmtPct },
  { key: 'usat_pct', label: 'Fenwick % (FF%)', fmt: fmtPct },
  { key: 'sat_rel', label: 'CF% relative', fmt: fmtSignedPct },
  { key: 'zone_start_pct_5v5', label: 'Offensive zone starts %', fmt: fmtPct },
  { key: 'ev_goals_for_pct', label: 'Even-strength goal share', fmt: fmtPct },
  { key: 'pp_points_per60', label: 'Power-play points / 60', fmt: fmt1 },
]

const ordinal = (n) => {
  const v = n % 100
  if (v >= 11 && v <= 13) return `${n}th`
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'}`
}

export default function Player() {
  const { id } = useParams()
  // Keep the id with the result so navigating between players shows "Loading" without a reset effect.
  const [result, setResult] = useState({ id: null, data: null, error: null })
  const ranks = useRankings(Number(id))
  const rank = (stat) => rankNote(ranks?.season?.[stat], 'season')

  useEffect(() => {
    fetch(`/api/skaters/${id}`)
      .then((r) => {
        if (r.status === 404) throw new Error('Player not found')
        if (!r.ok) throw new Error(`API returned ${r.status}`)
        return r.json()
      })
      .then((data) => setResult({ id, data, error: null }))
      .catch((error) => setResult({ id, data: null, error: error.message }))
  }, [id])

  const current = result.id === id ? result : { data: null, error: null }
  const { data, error } = current

  const back = <BackLink to="/skaters" />
  // No current-season data (retired or inactive): show the career page instead of an error.
  if (error === 'Player not found') return <CareerPlayer id={Number(id)} goalie={false} />
  if (error) return <main>{back}<p className="status">{error}</p></main>
  if (!data) return <main>{back}<PageSkeleton /></main>

  const { player: p, games, games_per_season, percentiles, peer_group, peer_count, peer_min_gp } = data

  return (
    <main>
      {back}
      <PlayerBanner
        p={p}
        stats={[
          { label: 'Points', value: p.points, rank: rank('points'), big: true },
          { label: 'Goals', value: p.goals, rank: rank('goals'), big: true },
          { label: 'Assists', value: p.assists, rank: rank('assists'), big: true },
          { label: 'GP', value: p.games_played, rank: rank('games_played'), big: true },
          { label: 'Point pace', value: fmt1(p.point_pace) },
          { label: `Last ${p.recent_games ?? 0} pace`, value: fmt1(p.recent_pace) },
          { label: '+/-', value: p.plus_minus, rank: rank('plus_minus') },
          { label: 'TOI / game', value: fmtToi(p.toi_per_game_sec) },
        ]}
      />

      <PageTabs
        tabs={[
          {
            id: 'stats',
            label: 'Stats',
            content: (
              <>
                <Context playerId={p.player_id} />
                <div className="player-overview">
                  <Explain playerId={p.player_id} name={p.name} />
                  <aside>
                    <Projection playerId={p.player_id} />
                    <Trophies playerId={p.player_id} />
                  </aside>
                </div>
                <Career playerId={p.player_id} />
                <Awards playerId={p.player_id} />
                <InternationalMedals playerId={p.player_id} />
                <Rankings playerId={p.player_id} kind="skater" />
                <Comparables playerId={p.player_id} />
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
                      <th className="left">Date</th>
                      <th className="left">Opponent</th>
                      <th title={describe('G')}>G</th><th title={describe('A')}>A</th><th title={describe('P')}>P</th><th title={describe('Shots')}>Shots</th><th title={describe('+/-')}>+/-</th><th title={describe('PIM')}>PIM</th><th title={describe('TOI')}>TOI</th><th title={describe('Hits')}>Hits</th><th title={describe('BLK')}>BLK</th><th title={describe('TK')}>TK</th><th title={describe('GV')}>GV</th>
                    </tr>
                  </thead>
                  <tbody>
                    {games.map((g) => (
                      <tr key={g.game_id}>
                        <td className="left">{g.game_date}</td>
                        <td className="left">{g.is_home ? 'vs' : '@'} {g.opponent}</td>
                        <td>{g.goals}</td><td>{g.assists}</td><td>{g.points}</td>
                        <td>{g.shots ?? '–'}</td><td>{g.plus_minus ?? '–'}</td>
                        <td>{g.pim ?? '–'}</td><td>{fmtToi(g.toi_sec)}</td>
                        <td>{g.hits ?? '–'}</td><td>{g.blocked_shots ?? '–'}</td>
                        <td>{g.takeaways ?? '–'}</td><td>{g.giveaways ?? '–'}</td>
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
                  {
                    id: 'profile',
                    label: 'Profile',
                    content: (
                      <>
                        <ScoutingCard playerId={p.player_id} />
                        <TrackingProfile playerId={p.player_id} />
                      </>
                    ),
                  },
                  {
                    id: 'role',
                    label: 'Role & usage',
                    content: (
                      <>
                        <RolePanel playerId={p.player_id} />

                        <h2>Possession &amp; special teams</h2>
                        <p className="sub">
                          5v5 shot attempts: {p.sat_for ?? '–'} for, {p.sat_against ?? '–'} against
                          ({p.usat_for ?? '–'} / {p.usat_against ?? '–'} excluding blocked shots). Percentile among {peer_count} {peer_group} with at
                          least {peer_min_gp} GP.
                        </p>
                        <StatCards stats={POSSESSION} p={p} percentiles={percentiles} />
                        <section className="tiles usage">
                          <Tile label="EV TOI" value={fmtToi(p.ev_toi_per_game)} />
                          <Tile label="PP TOI" value={fmtToi(p.pp_toi_per_game)} />
                          <Tile label="SH TOI" value={fmtToi(p.sh_toi_per_game)} />
                          <Tile label="PP points" value={p.pp_points} />
                          <Tile label="SH points" value={p.sh_points} />
                          <Tile label="Faceoff %" value={p.fo_win_pct == null ? null : `${fmtPct(p.fo_win_pct)}%`} />
                        </section>
                        <PenaltyKill p={p} />
                      </>
                    ),
                  },
                  {
                    id: 'defense',
                    label: 'Defense',
                    content: (
                      <>
                        <h2>Defensive game</h2>
                        <p className="sub">
                          Percentile among {peer_count} {peer_group} with at least {peer_min_gp} GP. Higher bar is
                          better for every stat, including giveaways.
                        </p>
                        <StatCards stats={DEFENSIVE} p={p} percentiles={percentiles} />
                        <DefenseProfile playerId={p.player_id} />
                      </>
                    ),
                  },
                  {
                    id: 'shooting',
                    label: 'Shooting',
                    content: (
                      <>
                        <ShooterZones playerId={p.player_id} />
                        <SkaterShots playerId={p.player_id} />
                        <LuckPanel playerId={p.player_id} />
                        <ScoreState playerId={p.player_id} />
                      </>
                    ),
                  },
                  {
                    id: 'teammates',
                    label: 'Teammates',
                    content: (
                      <>
                        <Linemates playerId={p.player_id} />
                        <Similar playerId={p.player_id} />
                      </>
                    ),
                  },
                ]}
              />
            ),
          },
          {
            id: 'trends',
            label: 'Trends',
            content: (
              <>
              <SkaterForm games={[...games].reverse()} />

              <PaceHistory base={`/api/skaters/${p.player_id}/pace-history`} title="This season vs. past seasons" selectable />

              <PossessionGuide />
              <div className="charts">
                <PaceChart
                  games={[...games].reverse()}
                  seasonGames={games_per_season}
                  pace={p.point_pace}
                />
                <GameBars games={[...games].reverse()} />
                <DefenseBars games={[...games].reverse()} />
                <CorsiChart games={[...games].reverse()} />
              </div>
              </>
            ),
          },
          { id: 'news', label: 'News', content: <PlayerNews playerId={p.player_id} name={p.name} team={p.team} /> },
        ]}
      />
    </main>
  )
}

function StatCards({ stats, p, percentiles }) {
  return (
    <div className="def-grid">
      {stats.map((d) => {
        const pct = percentiles[d.key]
        return (
          <div className="def-card" key={d.key}>
            <div className="def-top">
              <span>{d.label}</span>
              <strong>{p[d.key] == null ? '–' : d.fmt ? d.fmt(p[d.key]) : p[d.key]}</strong>
            </div>
            <div className="bar" title={pct == null ? '' : `${ordinal(pct)} percentile`}>
              <div style={{ width: `${pct ?? 0}%` }} />
            </div>
            <div className="def-foot">
              {pct == null ? 'no data' : `${ordinal(pct)} percentile`}
              {d.note && <em> · {d.note}</em>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function Tile({ label, value, rank }) {
  return (
    <div className="tile">
      <span>{label}</span>
      <strong>{value ?? '–'}</strong>
      {rank && <small className="tile-rank">{rank}</small>}
    </div>
  )
}
