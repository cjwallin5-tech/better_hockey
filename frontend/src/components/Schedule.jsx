import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const day = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
const time = (iso) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }) : '')

/** A team's recent results and upcoming games, each linking to the box score. */
export default function Schedule({ abbrev }) {
  const [state, setState] = useState({ abbrev: null, data: null })
  useEffect(() => {
    let ignore = false
    fetch(`/api/teams/${abbrev}/schedule`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setState({ abbrev, data }))
      .catch(() => !ignore && setState({ abbrev, data: null }))
    return () => { ignore = true }
  }, [abbrev])
  const d = state.abbrev === abbrev ? state.data : null
  if (!d || (d.results.length === 0 && d.upcoming.length === 0)) return null

  const opp = (g) => (g.home === abbrev ? ['vs', g.away] : ['@', g.home])
  return (
    <section>
      <h2>Schedule</h2>
      <div className="charts">
        <div>
          <h3 className="career-table-title">Recent results</h3>
          <div className="table-wrap">
            <table>
              <tbody>
                {d.results.map((g) => {
                  const [pre, o] = opp(g)
                  const us = g.home === abbrev ? g.home_score : g.away_score
                  const them = g.home === abbrev ? g.away_score : g.home_score
                  return (
                    <tr key={g.game_id}>
                      <td className="left">{day(g.game_date)}</td>
                      <td className="left">{pre} <Link to={`/team/${o}`}>{o}</Link></td>
                      <td className={g.result === 'W' ? 'accent' : ''}>{g.result}</td>
                      <td><Link to={`/game/${g.game_id}`}>{us}–{them}{g.last_period !== 'REG' ? ` ${g.last_period}` : ''}</Link></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
        <div>
          <h3 className="career-table-title">Upcoming</h3>
          <div className="table-wrap">
            <table>
              <tbody>
                {d.upcoming.map((g) => {
                  const [pre, o] = opp(g)
                  return (
                    <tr key={g.game_id}>
                      <td className="left">{day(g.game_date)}</td>
                      <td className="left">{pre} <Link to={`/team/${o}`}>{o}</Link></td>
                      <td>{g.state === 'LIVE' || g.state === 'CRIT' ? <Link to={`/game/${g.game_id}`}>Live</Link> : time(g.start_time)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  )
}
