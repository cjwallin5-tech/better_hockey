import { useEffect, useState } from 'react'
import BackLink from '../components/BackLink.jsx'
import { Link, useParams } from 'react-router-dom'
import { TeamLines } from '../components/Lines.jsx'
import PaceHistory from '../components/PaceHistory.jsx'
import Schedule from '../components/Schedule.jsx'
import { TeamShots } from '../components/Shots.jsx'
import SpecialTeams from '../components/SpecialTeams.jsx'
import TeamProspects from '../components/TeamProspects.jsx'
import PageTabs from '../components/PageTabs.jsx'
import TeamBanner from '../components/TeamBanner.jsx'
import { fmt1, fmtPct, fmtToi, STABLE_GP } from '../format.js'
import { describe } from '../glossary.js'
import PageSkeleton from '../components/Skeleton.jsx'

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
  const back = <BackLink to="/standings" />
  if (error) return <main>{back}<p className="status">{error}</p></main>
  if (!data) return <main>{back}<PageSkeleton /></main>

  const { team: t, roster, goalies } = data
  const lowPace = t.games_played < STABLE_GP

  return (
    <main>
      {back}
      <TeamBanner
        team={t}
        stats={[
          { label: 'Record', value: `${t.wins}-${t.losses}-${t.ot_losses}`, note: `${ordinal(t.division_rank)} in division`, big: true },
          { label: 'Points', value: t.points, note: `${ordinal(t.league_rank)} overall`, big: true },
          { label: 'Points pace', value: fmt1(t.points_pace), note: `${ordinal(t.conference_rank)} in conference`, big: true, dim: lowPace },
          { label: 'Goal diff', value: t.goal_diff > 0 ? `+${t.goal_diff}` : t.goal_diff, big: true },
          { label: 'GF / game', value: t.goals_for_pg?.toFixed(2) },
          { label: 'GA / game', value: t.goals_against_pg?.toFixed(2) },
          { label: 'Power play %', value: fmtPct(t.pp_pct) },
          { label: 'Penalty kill %', value: fmtPct(t.pk_pct) },
        ]}
      />

      <PageTabs
        tabs={[
          {
            id: 'overview',
            label: 'Overview',
            content: (
              <>
                <section className="card career-summary">
                  <dl className="career-more first">
                    <div><dt>Wins pace</dt><dd style={lowPace ? { opacity: 0.45 } : undefined}>{fmt1(t.wins_pace)}</dd></div>
                    <div><dt>Shots for / game</dt><dd>{fmt1(t.shots_for_pg)}</dd></div>
                    <div><dt>Shots against / game</dt><dd>{fmt1(t.shots_against_pg)}</dd></div>
                    <div><dt>Faceoff %</dt><dd>{fmtPct(t.fo_win_pct)}</dd></div>
                    <div><dt>Last 10</dt><dd>{t.l10_wins}-{t.l10_losses}-{t.l10_ot_losses}</dd></div>
                    <div><dt>Streak</dt><dd>{t.streak_code}{t.streak_count}</dd></div>
                    <div><dt>Home</dt><dd>{t.home_record ?? '–'}</dd></div>
                    <div><dt>Road</dt><dd>{t.road_record ?? '–'}</dd></div>
                  </dl>
                </section>
              <h2>Points pace vs. past seasons</h2>
              <PaceHistory base={`/api/teams/${t.abbrev}/pace-history`} title="Standings points by game" unit="points" />

              <Schedule abbrev={t.abbrev} />
              </>
            ),
          },
          {
            id: 'roster',
            label: 'Roster',
            content: (
              <>
              <h2>Roster</h2>
              <p className="sub">
                Skaters sorted by points. Players traded mid-season appear on both teams with their
                combined season totals.
              </p>
              <div className="table-wrap fit">
                <table>
                  <thead>
                    <tr>
                      <th className="left">Player</th><th className="left" title={describe('Pos')}>Pos</th>
                      <th title={describe('GP')}>GP</th><th title={describe('G')}>G</th><th title={describe('A')}>A</th><th title={describe('P')}>P</th><th title={describe('Pace')}>Pace</th>
                      <th title={describe('+/-')}>+/-</th><th title={describe('TOI')}>TOI</th><th title={describe('Hits')}>Hits</th><th title={describe('BLK')}>BLK</th><th title={describe('CF%')}>CF%</th>
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

              <h2>Goalies</h2>
              <p className="sub">
                Sorted by starts. GSAA is goals saved above a league-average goalie; Recent SV% covers
                each goalie's last 5 appearances.
              </p>
              {goalies.length === 0 ? (
                <p className="status">No goalie appearances yet.</p>
              ) : (
                <div className="table-wrap fit">
                  <table>
                    <thead>
                      <tr>
                        <th className="left">Goalie</th><th title={describe('GP')}>GP</th><th title={describe('GS')}>GS</th><th title={describe('W')}>W</th><th title={describe('L')}>L</th><th title={describe('OTL')}>OTL</th>
                        <th title={describe('SV%')}>SV%</th><th title={describe('GAA')}>GAA</th><th title={describe('GSAA')}>GSAA</th><th title={describe('SA/60')}>SA/60</th><th title={describe('QS%')}>QS%</th><th title={describe('SO')}>SO</th>
                        <th title={describe('Recent SV%')}>Recent SV%</th>
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

              <TeamProspects abbrev={t.abbrev} />
              </>
            ),
          },
          {
            id: 'lines',
            label: 'Lines & special teams',
            content: (
              <>
              <TeamLines abbrev={t.abbrev} />

              <SpecialTeams abbrev={t.abbrev} />
              </>
            ),
          },
          { id: 'shots', label: 'Shots', content: <TeamShots abbrev={t.abbrev} /> },
        ]}
      />
    </main>
  )
}
