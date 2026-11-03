import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PageTabs from '../components/PageTabs.jsx'
import LiveGames from '../components/LiveGames.jsx'
import Slate from '../components/Slate.jsx'
import TeamMark from '../components/TeamMark.jsx'
import { teamColor } from '../teamColors.js'
import TeamLogo from '../components/TeamLogo.jsx'
import { fmt1, fmtToi } from '../format.js'
import MovingUp from '../components/MovingUp.jsx'
import { describe } from '../glossary.js'
import PageSkeleton from '../components/Skeleton.jsx'

const longDay = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })
const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))
const signed = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`)

export default function Home() {
  const [records, setRecords] = useState(null)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/api/home')
      .then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`)
        return r.json()
      })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    fetch('/api/records').then((r) => (r.ok ? r.json() : null)).then(setRecords).catch(() => {})
  }, [])

  if (error) return <main><p className="status">Couldn't load the dashboard: {error}</p></main>
  if (!data) return <main><PageSkeleton cards /></main>

  const gs = data.games_per_season
  const player = (p) => <Link to={`/player/${p.player_id}`}>{p.name}</Link>
  const lead = data.point_pace[0]
  const streak = data.hot[0]
  const bestTeam = data.teams[0]
  const goalie = data.goalies[0]
  const spot = [
    lead && { label: 'Point pace leader', num: fmt1(lead.pace), who: `${lead.name} · ${lead.team}`, team: lead.team, to: `/player/${lead.player_id}` },
    streak && { label: 'Longest point streak', num: streak.streak, unit: 'games', who: `${streak.name} · ${streak.team}`, team: streak.team, to: `/player/${streak.player_id}` },
    bestTeam && { label: 'Best team by pace', num: fmt1(bestTeam.points_pace), who: `${bestTeam.name}`, team: bestTeam.abbrev, to: `/team/${bestTeam.abbrev}` },
    goalie && { label: 'Top goalie by GSAA', num: signed(goalie.gsaa), who: `${goalie.name} · ${goalie.team}`, team: goalie.team, to: `/goalie/${goalie.player_id}` },
  ].filter(Boolean)

  return (
    <main>
      <header className="hero">
        <h1>NHL Stats</h1>
        <p>Point pace, defensive stats and career context the official site doesn't show.</p>
        <div className="spotlight">
          {spot.map((t) => (
            <Link key={t.label} to={t.to} className="spot" style={{ '--team': teamColor(t.team) }}>
              <span className="spot-label">{t.label}</span>
              <strong className="spot-num">{t.num}{t.unit && <small>{t.unit}</small>}</strong>
              <span className="spot-who"><TeamMark abbrev={t.team} size={20} />{t.who}</span>
            </Link>
          ))}
        </div>
      </header>

      <LiveGames />

      {data.upcoming.length > 0 && (
        <section className="block" aria-label="Upcoming games">
          <div className="eyebrow">{data.upcoming_day ? longDay(data.upcoming_day) : 'Upcoming'}</div>
          <Slate games={data.upcoming} />
        </section>
      )}

      {data.games.length > 0 && (
        <section className="block" aria-label="Last night's results">
          <div className="eyebrow">Final scores, {longDay(data.last_game_day)}</div>
          <div className="finals">
            {data.games.map((g) => {
              const awayWon = g.away_score > g.home_score
              const line = (abbrev, score, won) => (
                <div className={`result-row${won ? ' win' : ''}`}>
                  <TeamMark abbrev={abbrev} size={22} />
                  <Link to={`/team/${abbrev}`}>{abbrev}</Link>
                  <strong>{score}</strong>
                </div>
              )
              return (
                <article key={g.game_id} className="result" style={{ '--away': teamColor(g.away), '--home': teamColor(g.home) }}>
                  {line(g.away, g.away_score, awayWon)}
                  {line(g.home, g.home_score, !awayWon)}
                  <Link to={`/game/${g.game_id}`} className="result-foot">{g.last_period === 'REG' ? 'Final' : `Final/${g.last_period}`}</Link>
                </article>
              )
            })}
          </div>
        </section>
      )}

      <div className="home-grid block">
        {data.performers.length > 0 && (
          <section className="card">
            <div className="eyebrow">Top performers</div>
            <table className="mini">
              <tbody>
                {data.performers.slice(0, 5).map((p) => (
                  <tr key={`${p.player_id}-${p.game_id}`}>
                    <td>{player(p)} <span className="muted">{p.team} {p.is_home ? 'vs' : '@'} {p.opponent}</span></td>
                    <td className="num">{p.goals}G {p.assists}A</td>
                    <td className="num accent">{p.points} pts</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {data.goalie_nights.length > 0 && (
          <section className="card">
            <div className="eyebrow">Goalie standouts</div>
            <table className="mini">
              <tbody>
                {data.goalie_nights.map((g) => (
                  <tr key={g.player_id}>
                    <td><Link to={`/goalie/${g.player_id}`}>{g.name}</Link> <span className="muted">{g.team} vs {g.opponent}</span></td>
                    <td className="num">{g.saves}/{g.shots_against}</td>
                    <td className="num accent">{sv(g.save_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        <section className="card">
          <div className="eyebrow">Top teams</div>
          <table className="mini">
            <tbody>
              {data.teams.map((t) => (
                <tr key={t.abbrev}>
                  <td className="team-line"><TeamLogo team={t} size={20} /> <Link to={`/team/${t.abbrev}`}>{t.name}</Link></td>
                  <td className="num">{t.wins}-{t.losses}-{t.ot_losses}</td>
                  <td className="num accent">{fmt1(t.points_pace)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small"><Link to="/standings">Full standings →</Link></p>
        </section>
      </div>

      <PageTabs
        tabs={[
          {
            id: 'streaks',
            label: 'Hot & cold',
            content: (
              <div className="home-grid">
        <section className="card">
          <h2>Hot streaks</h2>
          <p className="muted small">Consecutive games with a point.</p>
          <StreakTable rows={data.hot} unit="games" />
          <h2 className="gap">Cold spells</h2>
          <p className="muted small">Top-six forwards (17+ minutes a night) without a point in 3+ games.</p>
          <StreakTable rows={data.cold} unit="games" empty="Nobody fits right now." />
        </section>

              </div>
            ),
          },
          {
            id: 'rising',
            label: 'Moving up',
            content: <div className="home-grid"><MovingUp /></div>,
          },
          {
            id: 'pace',
            label: 'Pace leaders',
            content: <div className="home-grid">
        <section className="card">
          <h2>Pace leaders</h2>
          <p className="muted small">Players with at least {data.min_gp} GP, projected to {gs} games.</p>
          <h3>Points</h3>
          <PaceTable rows={data.point_pace} />
          <h3>Goals</h3>
          <PaceTable rows={data.goal_pace} />
        </section>

            </div>,
          },
          {
            id: 'goalies',
            label: 'Goaltending',
            content: <div className="home-grid">
        <section className="card">
          <h2>Goaltending leaders</h2>
          <p className="muted small">By goals saved above average.</p>
          <table className="mini">
            <thead><tr><th /><th className="num" title={describe('SV%')}>SV%</th><th className="num" title={describe('GAA')}>GAA</th><th className="num" title={describe('GSAA')}>GSAA</th></tr></thead>
            <tbody>
              {data.goalies.map((g) => (
                <tr key={g.player_id}>
                  <td><Link to={`/goalie/${g.player_id}`}>{g.name}</Link> <span className="muted">{g.team}</span></td>
                  <td className="num">{sv(g.save_pct)}</td>
                  <td className="num">{g.gaa?.toFixed(2)}</td>
                  <td className="num accent">{signed(g.gsaa)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small"><Link to="/goalies">All goalies →</Link></p>
        </section>

            </div>,
          },
          ...(records
            ? [{
                id: 'records',
                label: 'Record watch',
                content: <div className="home-grid">
        
          <section className="card record-card">
            <h2>Record watch</h2>
            <p className="muted small">
              Who's on pace (projected to {gs} games) against the best single seasons ever. Very early
              in a season these paces swing wildly.
            </p>
            {['points', 'goals', 'assists'].map((stat) => {
              const r = records.records[stat]
              return (
                <div key={stat} className="record-row">
                  <h3>
                    {stat[0].toUpperCase() + stat.slice(1)} record: {r.record.value}{' '}
                    <span className="muted">
                      {r.record.name}, {String(r.record.season_id).slice(0, 4)}-{String(r.record.season_id).slice(6)} ({r.record.games} GP)
                    </span>
                  </h3>
                  <table className="mini">
                    <tbody>
                      {r.on_pace.slice(0, 3).map((p) => (
                        <tr key={p.player_id}>
                          <td>{player(p)} <span className="muted">{p.team} · {p.value} in {p.games_played}</span></td>
                          <td className="num accent">{fmt1(p.pace)}</td>
                          <td className="num">{p.pace >= r.record.value ? <span className="badge">ahead of record</span> : `${Math.round((100 * p.pace) / r.record.value)}% of record`}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            })}
          </section>
                </div>,
              }]
            : []),
        ]}
      />
    </main>
  )

  function StreakTable({ rows, empty = 'Nobody yet.' }) {
    if (!rows.length) return <p className="status">{empty}</p>
    return (
      <table className="mini">
        <tbody>
          {rows.map((p) => (
            <tr key={p.player_id}>
              <td>{player(p)} <span className="muted">{p.team} · {p.position}</span></td>
              <td className="num">{p.goals}G {p.assists}A in {p.games_played}</td>
              <td className="num accent">{p.streak} {p.streak === 1 ? 'game' : 'games'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  function PaceTable({ rows }) {
    return (
      <table className="mini">
        <tbody>
          {rows.map((p) => (
            <tr key={p.player_id}>
              <td>{player(p)} <span className="muted">{p.team} · {fmtToi(p.toi_per_game_sec)}</span></td>
              <td className="num">{p.goals}G {p.assists}A in {p.games_played}</td>
              <td className="num accent">{fmt1(p.pace)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }
}
