import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const dayName = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short' })
const pct = (p) => (p == null ? '–' : `${Math.round(p * 100)}%`)

/**
 * Rostered goalies' chances of starting each game this week. Goalies only score when they start, so
 * expected starts matter more than games. A guess from recent starts and back-to-backs until the NHL
 * confirms a starter.
 */
export default function GoalieStarts({ players }) {
  const ids = players.filter((p) => p.kind === 'goalie').map((p) => p.id).join(',')
  const [state, setState] = useState({ ids: null, data: null })

  useEffect(() => {
    if (!ids) return undefined
    let ignore = false
    fetch(`/api/probable-goalies/week?ids=${ids}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setState({ ids, data }))
      .catch(() => !ignore && setState({ ids, data: null }))
    return () => { ignore = true }
  }, [ids])

  const data = state.ids === ids ? state.data : null
  if (!ids || !data || data.goalies.length === 0) return null

  return (
    <section>
      <h2>Goalie starts this week</h2>
      <p className="sub">
        Each percentage is the chance that goalie starts that game, a guess from his team's recent starts and
        back-to-backs (B2B). Later days build on earlier guesses, so they are less certain. A check mark means the NHL has
        confirmed the starter. Injuries and rest days we can't see are not accounted for.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th className="left">Goalie</th><th className="left">Team</th><th title="Sum of the start chances below">Expected starts</th><th className="left">Games</th></tr>
          </thead>
          <tbody>
            {data.goalies.map((g) => (
              <tr key={g.player_id}>
                <td className="left"><Link to={`/goalie/${g.player_id}`}>{g.name}</Link></td>
                <td className="left">{g.team}</td>
                <td className="accent">{g.expected_starts == null ? '–' : g.expected_starts.toFixed(1)}</td>
                <td className="left">
                  {g.games.length === 0 ? <span className="muted">No games</span> : g.games.map((x, i) => (
                    <span key={x.game_id} className="goalie-start">
                      {i > 0 && ' · '}
                      {dayName(x.date)} {x.home_game ? 'vs' : '@'} {x.opponent}{x.back_to_back ? <sup title="Second game in two nights"> B2B</sup> : null}{' '}
                      <strong className={x.probability >= 0.7 || x.confirmed ? 'accent' : 'muted'}>{x.confirmed ? '✓' : pct(x.probability)}</strong>
                    </span>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
