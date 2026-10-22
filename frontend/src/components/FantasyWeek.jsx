import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MatchupTag, pctOff, ratioLabel, useMatchupTeams } from './Matchups.jsx'
import RestBadge from './RestBadge.jsx'
import { describe } from '../glossary.js'

const dayName = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short' })

// A game's own ratio already includes the rest adjustment (see matchups.py); the opponent's season-long rating is the fallback.
const ratioFor = (teams, g, kind) => g[kind === 'goalie' ? 'goalie_ratio' : 'skater_ratio'] ?? teams.get(g.opponent)?.[kind === 'goalie' ? 'goalie_ratio' : 'skater_ratio'] ?? null
const labelFor = (teams, g, kind) => g[kind === 'goalie' ? 'goalie_label' : 'skater_label'] ?? teams.get(g.opponent)?.[kind === 'goalie' ? 'goalie_label' : 'skater_label'] ?? null

/** One player's week in a cell: the average matchup over their games, with the sum of how far each is from average. */
function WeekMatchup({ games, kind, teams }) {
  if (!teams || games.length === 0) return <span className="muted">–</span>
  const ratios = games.map((g) => ratioFor(teams, g, kind)).filter((r) => r != null)
  if (ratios.length === 0) return <span className="muted">–</span>
  const avg = ratios.reduce((t, r) => t + r, 0) / ratios.length
  const index = ratios.reduce((t, r) => t + r - 1, 0)
  const lab = ratioLabel(avg)
  return (
    <span title={`Average opponent is ${pctOff(avg)} vs average over ${ratios.length} game${ratios.length === 1 ? '' : 's'}; opportunity index ${index > 0 ? '+' : ''}${index.toFixed(2)}`}>
      {pctOff(avg)} <MatchupTag ratio={avg} label={lab} who={kind === 'goalie' ? 'goalies' : 'skaters'} />
    </span>
  )
}

/** Roster alerts (lineup gaps, trades) and each player's team games over the next week. */
export default function FantasyWeek({ players }) {
  const key = players.map((p) => p.id).join(',')
  const [state, setState] = useState({ key: null, data: null })
  const teams = useMatchupTeams()

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
            <tr><th className="left">Player</th><th className="left" title={describe('Team')}>Team</th><th>Games</th><th title="How favorable this week's games are on average: skaters face defense and goalie, goalies face offense, and a back-to-back or a rest edge moves a game by a few percent">Week matchup</th><th className="left">Schedule</th></tr>
          </thead>
          <tbody>
            {rows.map(({ p, w }) => (
              <tr key={p.id}>
                <td className="left"><Link to={`/${p.kind === 'goalie' ? 'goalie' : 'player'}/${p.id}`}>{p.name}</Link></td>
                <td className="left">{w.team}</td>
                <td className={w.games.length === most && most > 0 ? 'accent' : ''}>{w.games.length}</td>
                <td><WeekMatchup games={w.games} kind={p.kind} teams={teams} /></td>
                <td className="left">
                  {w.games.length === 0
                    ? <span className="muted">No games</span>
                    : w.games.map((g) => (
                      <span key={g.game_id} style={{ marginRight: 10, whiteSpace: 'nowrap' }}>
                        {dayName(g.game_date)} {g.home_game ? 'vs' : '@'} {g.opponent}
                        <RestBadge kind={g.rest} />
                        {teams && <MatchupTag ratio={ratioFor(teams, g, p.kind)} label={labelFor(teams, g, p.kind)} who={p.kind === 'goalie' ? 'goalies' : 'skaters'} />}
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
