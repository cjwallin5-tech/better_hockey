import Info from './Info.jsx'
import { seasonLabel } from '../career.js'
import { useJson } from '../lists.js'

/** The seasons a player led the NHL in goals, assists and points, and how often they were in the top 5 and top 10 (see backend/finishes.py). */
export default function LeagueFinishes({ playerId }) {
  const d = useJson(`/api/players/${playerId}/finishes`)
  if (!d || d.stats.length === 0) return null
  return (
    <section>
      <h2>
        League finishes
        <Info label="League finishes">
          Where the player ranked among all NHL skaters in each finished season, regular season only. A tie shares a place, so two players can both
          lead the league. The current season is left out until it ends.
        </Info>
      </h2>
      <div className="table-wrap fit">
        <table className="finishes">
          <thead>
            <tr><th className="left">Stat</th><th className="left" title="Seasons the player ranked first among all NHL skaters in this stat (a tie counts for each)">Led the NHL</th><th title="Seasons finishing in the top 5, including those leading the league">Top 5</th><th title="Seasons finishing in the top 10, including the top 5">Top 10</th></tr>
          </thead>
          <tbody>
            {d.stats.map((s) => (
              <tr key={s.stat}>
                <td className="left">{s.label}</td>
                <td className="left">
                  {s.led.length === 0 ? <span className="muted">–</span> : (
                    <><strong>{s.led.length}×</strong> <span className="muted">{s.led.map((x) => seasonLabel(x.season_id)).join(', ')}</span></>
                  )}
                </td>
                <td>{s.top5}</td>
                <td>{s.top10}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
