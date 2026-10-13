import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const dayName = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short' })

/** Roster alerts (lineup gaps, trades) and each player's team games over the next week. */
export default function FantasyWeek({ players }) {
  const key = players.map((p) => p.id).join(',')
  const [state, setState] = useState({ key: null, data: null })

  useEffect(() => {
    if (!key) return
    let ignore = false
    fetch(`/api/fantasy/week?ids=${key}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setState({ key, data }))
      .catch(() => !ignore && setState({ key, data: null }))
    return () => { ignore = true }
  }, [key])

  const d = state.key === key ? state.data : null
  if (!key || !d) return null
  const rows = players.map((p) => ({ p, w: d.players[p.id] })).filter((r) => r.w)
  if (rows.length === 0) return null

  const most = Math.max(...rows.map((r) => r.w.games.length))
  const alerts = rows.filter(({ w }) => w.games_out >= 1 || w.traded)

  return (
    <section>
      <h2>This week</h2>
      {alerts.length > 0 && (
        <ul className="roster-alerts">
          {alerts.map(({ p, w }) => (
            <li key={p.id} className="warn">
              <Link to={`/${p.kind === 'goalie' ? 'goalie' : 'player'}/${p.id}`}>{p.name}</Link>
              {w.games_out >= 1 && <> hasn't played in {w.games_out} of {w.team}'s last games. The NHL feed doesn't say why (injury, scratch or demotion).</>}
              {w.traded && <> changed teams this season.</>}
            </li>
          ))}
        </ul>
      )}
      <p className="sub">Games from {dayName(d.from)} {d.from.slice(5)} to {dayName(d.to)} {d.to.slice(5)}. More games means more chances to score.</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th className="left">Player</th><th className="left">Team</th><th>Games</th><th className="left">Schedule</th></tr>
          </thead>
          <tbody>
            {rows.map(({ p, w }) => (
              <tr key={p.id}>
                <td className="left"><Link to={`/${p.kind === 'goalie' ? 'goalie' : 'player'}/${p.id}`}>{p.name}</Link></td>
                <td className="left">{w.team}</td>
                <td className={w.games.length === most && most > 0 ? 'accent' : ''}>{w.games.length}</td>
                <td className="left">
                  {w.games.length === 0
                    ? <span className="muted">No games</span>
                    : w.games.map((g) => `${dayName(g.game_date)} ${g.home_game ? 'vs' : '@'} ${g.opponent}`).join(' · ')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
