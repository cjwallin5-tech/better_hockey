import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import PageTabs from '../components/PageTabs.jsx'
import Career from '../components/Career.jsx'
import Trophies from '../components/Trophies.jsx'
import Rankings, { rankNote, useRankings } from '../components/Rankings.jsx'
import FantasyStar from '../components/FantasyStar.jsx'
import WatchButton from '../components/WatchButton.jsx'
import CareerPlayer from './CareerPlayer.jsx'
import Context from '../components/Context.jsx'
import { Linemates } from '../components/Lines.jsx'
import { SkaterShots } from '../components/Shots.jsx'
import PaceHistory from '../components/PaceHistory.jsx'
import Similar from '../components/Similar.jsx'
import Comparables from '../components/Comparables.jsx'
import DefenseProfile from '../components/DefenseProfile.jsx'
import TrackingProfile from '../components/TrackingProfile.jsx'
import LuckPanel from '../components/Luck.jsx'
import Projection from '../components/Projection.jsx'
import Explain from '../components/Explain.jsx'
import { SkaterForm } from '../components/Form.jsx'
import { RolePanel } from '../components/Roles.jsx'
import { CorsiChart, DefenseBars, GameBars, PaceChart } from '../components/Charts.jsx'
import Flag from '../components/Flag.jsx'
import Headshot from '../components/Headshot.jsx'
import PlayerBio from '../components/PlayerBio.jsx'
import Awards from '../components/Awards.jsx'
import { describe } from '../glossary.js'

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

  const back = <Link to="/skaters" className="back">← All skaters</Link>
  // No current-season data (retired or inactive): show the career page instead of an error.
  if (error === 'Player not found') return <CareerPlayer id={Number(id)} goalie={false} />
  if (error) return <main>{back}<p className="status">{error}</p></main>
  if (!data) return <main>{back}<p className="status">Loading…</p></main>

  const { player: p, games, games_per_season, percentiles, peer_group, peer_count, peer_min_gp } = data

  return (
    <main>
      {back}
      <header className="player-head">
        <Headshot playerId={p.player_id} name={p.name} />
        <div>
        <h1>
          <Flag playerId={p.player_id} />{p.name}{' '}
          <span>
            {p.team?.split(',').map((abbr, i) => (
              <span key={abbr}>{i > 0 && ', '}<Link to={`/team/${abbr}`}>{abbr}</Link></span>
            ))}{' '}
            · {p.position}
          </span>
        </h1>
        <PlayerBio playerId={p.player_id} />
        <p className="header-actions">
          <FantasyStar player={{ id: p.player_id, kind: 'skater', name: p.name }} />
          <WatchButton kind="player" refId={p.player_id} name={p.name} />
          <Link to={`/compare?ids=${p.player_id}`}>Compare with other players →</Link>
        </p>
        </div>
      </header>

      <Context playerId={p.player_id} />
      <Explain playerId={p.player_id} />
      <Projection playerId={p.player_id} />
      <Trophies playerId={p.player_id} />

      <section className="tiles">
        <Tile label="GP" value={p.games_played} rank={rank('games_played')} />
        <Tile label="Goals" value={p.goals} rank={rank('goals')} />
        <Tile label="Assists" value={p.assists} rank={rank('assists')} />
        <Tile label="Points" value={p.points} rank={rank('points')} />
        <Tile label="Point pace" value={fmt1(p.point_pace)} />
        <Tile
          label={`Last ${p.recent_games ?? 0} pace`}
          value={fmt1(p.recent_pace)}
        />
        <Tile label="+/-" value={p.plus_minus} rank={rank('plus_minus')} />
        <Tile label="TOI / game" value={fmtToi(p.toi_per_game_sec)} />
      </section>

      <PageTabs
        tabs={[
          {
            id: 'stats',
            label: 'Stats',
            content: (
              <>
                <Career playerId={p.player_id} />
                <Awards playerId={p.player_id} />
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
              <>
              <RolePanel playerId={p.player_id} />

              <h2>Defensive game</h2>
              <p className="sub">
                Percentile among {peer_count} {peer_group} with at least {peer_min_gp} GP. Higher bar is
                better for every stat, including giveaways.
              </p>
              <StatCards stats={DEFENSIVE} p={p} percentiles={percentiles} />

              <h2>Possession &amp; special teams</h2>
              <p className="sub">
                5v5 shot attempts: {p.sat_for ?? '–'} for, {p.sat_against ?? '–'} against
                ({p.usat_for ?? '–'} / {p.usat_against ?? '–'} excluding blocked shots). Same peer
                group as above.
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

              <DefenseProfile playerId={p.player_id} />

              <LuckPanel playerId={p.player_id} />

              <TrackingProfile playerId={p.player_id} />

              <SkaterShots playerId={p.player_id} />

              <Linemates playerId={p.player_id} />

              <Similar playerId={p.player_id} />
              </>
            ),
          },
          {
            id: 'trends',
            label: 'Trends',
            content: (
              <>
              <SkaterForm games={[...games].reverse()} />

              <PaceHistory base={`/api/skaters/${p.player_id}/pace-history`} title="This season vs. past seasons" selectable />

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
