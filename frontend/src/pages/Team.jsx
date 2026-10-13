import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { TeamLines } from '../components/Lines.jsx'
import PaceHistory from '../components/PaceHistory.jsx'
import Schedule from '../components/Schedule.jsx'
import { TeamShots } from '../components/Shots.jsx'
import TeamLogo from '../components/TeamLogo.jsx'
import { fmt1, fmtPct, fmtToi, STABLE_GP } from '../format.js'

const fmtSv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))
const fmtSigned = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`)

const ordinal = (n) => {
  const v = n % 100
  if (v >= 11 && v <= 13) return `${n}th`
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'}`
}

export default function Team() {
  const { abbrev } = useParams()
  const [result, setResult] = useState({ abbrev: null, data: null, error: null })

  useEffect(() => {
    fetch(`/api/teams/${abbrev}`)
      .then((r) => {
        if (r.status === 404) throw new Error('Team not found')
        if (!r.ok) throw new Error(`API returned ${r.status}`)
        return r.json()
      })
      .then((data) => setResult({ abbrev, data, error: null }))
      .catch((error) => setResult({ abbrev, data: null, error: error.message }))
  }, [abbrev])

  const { data, error } = result.abbrev === abbrev ? result : { data: null, error: null }
  const back = <Link to="/standings" className="back">← Standings</Link>
  if (error) return <main>{back}<p className="status">{error}</p></main>
  if (!data) return <main>{back}<p className="status">Loading…</p></main>

  const { team: t, roster, goalies } = data
  const lowPace = t.games_played < STABLE_GP

  return (
    <main>
      {back}
      <header className="team-head">
        <TeamLogo team={t} size={56} />
        <div>
          <h1>{t.name}</h1>
          <p>
            {t.division} Division · {t.conference} Conference · {ordinal(t.division_rank)} in
            division, {ordinal(t.conference_rank)} in conference, {ordinal(t.league_rank)} overall
          </p>
        </div>
      </header>

      <section className="tiles">
        <Tile label="Record (W-L-OTL)" value={`${t.wins}-${t.losses}-${t.ot_losses}`} />
        <Tile label="Points" value={t.points} />
        <Tile label="Points pace" value={fmt1(t.points_pace)} low={lowPace} />
        <Tile label="Wins pace" value={fmt1(t.wins_pace)} low={lowPace} />
        <Tile label="Goals for / game" value={t.goals_for_pg?.toFixed(2)} />
        <Tile label="Goals against / game" value={t.goals_against_pg?.toFixed(2)} />
        <Tile label="Goal diff" value={t.goal_diff > 0 ? `+${t.goal_diff}` : t.goal_diff} />
        <Tile label="Power play %" value={fmtPct(t.pp_pct)} />
        <Tile label="Penalty kill %" value={fmtPct(t.pk_pct)} />
        <Tile label="Shots for / game" value={fmt1(t.shots_for_pg)} />
        <Tile label="Shots against / game" value={fmt1(t.shots_against_pg)} />
        <Tile label="Faceoff %" value={fmtPct(t.fo_win_pct)} />
        <Tile label="Last 10" value={`${t.l10_wins}-${t.l10_losses}-${t.l10_ot_losses}`} />
        <Tile label="Streak" value={`${t.streak_code}${t.streak_count}`} />
        <Tile label="Home" value={t.home_record} />
        <Tile label="Road" value={t.road_record} />
      </section>

      <h2>Points pace vs. past seasons</h2>
      <PaceHistory base={`/api/teams/${t.abbrev}/pace-history`} title="Standings points by game" unit="points" />

      <Schedule abbrev={t.abbrev} />

      <TeamLines abbrev={t.abbrev} />

      <TeamShots abbrev={t.abbrev} />

      <h2>Goalies</h2>
      <p className="sub">
        Sorted by starts. GSAA is goals saved above a league-average goalie; Recent SV% covers
        each goalie's last 5 appearances.
      </p>
      {goalies.length === 0 ? (
        <p className="status">No goalie appearances yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="left">Goalie</th><th>GP</th><th>GS</th><th>W</th><th>L</th><th>OTL</th>
                <th>SV%</th><th>GAA</th><th>GSAA</th><th>SA/60</th><th>QS%</th><th>SO</th>
                <th>Recent SV%</th>
              </tr>
            </thead>
            <tbody>
              {goalies.map((g) => (
                <tr key={g.player_id}>
                  <td className="left"><Link to={`/goalie/${g.player_id}`}>{g.name}</Link></td>
                  <td>{g.games_played}</td><td>{g.games_started}</td>
                  <td>{g.wins}</td><td>{g.losses}</td><td>{g.ot_losses}</td>
                  <td className="accent">{fmtSv(g.save_pct)}</td>
                  <td>{g.gaa?.toFixed(2) ?? '–'}</td>
                  <td className="accent">{fmtSigned(g.gsaa)}</td>
                  <td>{fmt1(g.shots_against_per60)}</td>
                  <td>{fmtSv(g.quality_start_pct)}</td>
                  <td>{g.shutouts}</td>
                  <td>{fmtSv(g.recent_save_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Roster</h2>
      <p className="sub">
        Skaters sorted by points. Players traded mid-season appear on both teams with their
        combined season totals.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left">Player</th><th className="left">Pos</th>
              <th>GP</th><th>G</th><th>A</th><th>P</th><th>Pace</th>
              <th>+/-</th><th>TOI</th><th>Hits</th><th>BLK</th><th>CF%</th>
            </tr>
          </thead>
          <tbody>
            {roster.map((p) => (
              <tr key={p.player_id}>
                <td className="left"><Link to={`/player/${p.player_id}`}>{p.name}</Link></td>
                <td className="left">{p.position}</td>
                <td>{p.games_played}</td><td>{p.goals}</td><td>{p.assists}</td><td>{p.points}</td>
                <td className={'accent' + (p.games_played < STABLE_GP ? ' low' : '')}>{fmt1(p.point_pace)}</td>
                <td>{p.plus_minus ?? '–'}</td><td>{fmtToi(p.toi_per_game_sec)}</td>
                <td>{p.hits ?? '–'}</td><td>{p.blocked_shots ?? '–'}</td><td>{fmtPct(p.sat_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  )
}

function Tile({ label, value, low }) {
  return (
    <div className="tile" title={low ? 'Small sample: treat this pace with caution' : undefined}>
      <span>{label}</span>
      <strong style={low ? { opacity: 0.45 } : undefined}>{value ?? '–'}</strong>
    </div>
  )
}
