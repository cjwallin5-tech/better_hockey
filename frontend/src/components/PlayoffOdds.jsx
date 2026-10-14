import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import TeamLogo from './TeamLogo.jsx'

const pct = (p) => (p >= 0.995 ? '>99%' : p < 0.005 ? '<1%' : `${Math.round(p * 100)}%`)

/** Simulated chances of making the playoffs, per conference. `teams` supplies logos and names. */
export default function PlayoffOdds({ teams }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    fetch('/api/playoff-odds')
      .then((r) => { if (!r.ok) throw new Error(`API returned ${r.status}`); return r.json() })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <p className="status">Couldn't load playoff odds: {error}</p>
  if (!data) return <p className="status">Running the simulation…</p>

  const byAbbrev = new Map(teams.map((t) => [t.abbrev, t]))
  const conferences = ['Eastern', 'Western']
  return (
    <>
      <p className="sub">
        Odds come from playing out the {data.games_remaining.toLocaleString()} remaining games {data.sims.toLocaleString()} times.
        Each team is rated on goal differential per game, pulled toward average while few games are played, with a small home-ice
        edge. It's a model, not a prediction, and it's very uncertain early in the season. The top 3 in each division plus 2 wild
        cards per conference make it.
      </p>
      {conferences.map((conf) => {
        const rows = data.teams.filter((t) => t.conference === conf).sort((a, b) => b.make_playoffs - a.make_playoffs || b.points - a.points)
        return (
          <section key={conf} className="standings-group">
            <h2>{conf} Conference</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th className="left">Team</th><th>GP</th><th>PTS</th>
                    <th>Projected pts</th><th>Likely range</th><th>Make playoffs</th><th>Win division</th><th>Best record</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((t) => {
                    const logo = byAbbrev.get(t.abbrev)
                    return (
                      <tr key={t.abbrev}>
                        <td className="left team-cell">
                          {logo && <TeamLogo team={logo} />}
                          <Link to={`/team/${t.abbrev}`}>{t.name}</Link>
                        </td>
                        <td>{t.games_played}</td><td><strong>{t.points}</strong></td>
                        <td>{Math.round(t.exp_points)}</td>
                        <td className="muted">{Math.round(t.p10_points)}–{Math.round(t.p90_points)}</td>
                        <td className="odds-cell">
                          <div className="bar" title={`${(t.make_playoffs * 100).toFixed(1)}%`}><div style={{ width: `${t.make_playoffs * 100}%` }} /></div>
                          <strong className="accent">{pct(t.make_playoffs)}</strong>
                        </td>
                        <td>{pct(t.win_division)}</td>
                        <td>{pct(t.best_record)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )
      })}
      <p className="sub">"Likely range" is the middle 80% of simulated final point totals.</p>
    </>
  )
}
