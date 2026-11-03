import { Link } from 'react-router-dom'
import TeamMark from './TeamMark.jsx'
import { teamColor } from '../teamColors.js'

const longDate = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
const periodOf = (sec) => Math.min(Math.floor((sec - 1) / 1200) + 1, 4)

/** Goals by period for each team, from the goal list: { WPG: [0, 0, 0, 0], CAR: [1, 3, 3, 0] } (the fourth slot is overtime). */
export function lineScore(goals, sides) {
  const out = Object.fromEntries(sides.map((s) => [s, [0, 0, 0, 0]]))
  for (const x of goals) if (out[x.team]) out[x.team][periodOf(x.time_sec) - 1] += 1
  return out
}

/**
 * The top of a game page, a scoreboard: both teams with the score (the winner at full strength), the status and place, and a
 * line score by period. Split team-colour stripe along the top, away on the left as in the schedule.
 */
export default function GameBanner({ g, score, finished, goals, teams, hasShots }) {
  const sides = [g.away, g.home]
  const winner = finished ? (score[g.away] > score[g.home] ? g.away : score[g.home] > score[g.away] ? g.home : null) : null
  const status = finished ? (g.last_period === 'REG' ? 'Final' : `Final / ${g.last_period}`) : g.state
  const ls = lineScore(goals, sides)
  const ot = ls[g.away][3] + ls[g.home][3] > 0
  const cols = ot ? ['1', '2', '3', 'OT'] : ['1', '2', '3']
  return (
    <header className="game-banner" style={{ '--away': teamColor(g.away), '--home': teamColor(g.home) }}>
      <div className="gb-status">{status} · {longDate(g.game_date)}</div>
      <div className="gb-teams">
        {sides.map((s, i) => (
          <div key={s} className={`gb-team ${i === 0 ? 'away' : 'home'}${winner && winner !== s ? ' lost' : ''}`}>
            <TeamMark abbrev={s} size={84} />
            <Link to={`/team/${s}`} className="gb-abbrev">{s}</Link>
            <strong className="gb-score">{score[s] ?? '–'}</strong>
          </div>
        ))}
      </div>
      <p className="gb-meta">
        {g.venue ? `${g.venue} · ` : ''}<Link to={`/head-to-head?a=${g.home}&b=${g.away}`}>Head-to-head history</Link>
      </p>
      {finished && goals.length + 0 >= 0 && (
        <table className="linescore">
          <thead>
            <tr><th className="left" />{cols.map((c) => <th key={c}>{c}</th>)}<th>T</th>{hasShots && <th>SOG</th>}</tr>
          </thead>
          <tbody>
            {sides.map((s) => (
              <tr key={s}>
                <td className="left">{s}</td>
                {cols.map((c, i) => <td key={c}>{ls[s][i]}</td>)}
                <td><strong>{score[s] ?? '–'}</strong></td>
                {hasShots && <td>{teams[s]?.on_goal ?? '–'}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </header>
  )
}
