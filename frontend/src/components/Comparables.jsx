import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CompareChart } from './Charts.jsx'
import { seasonLabel } from '../career.js'

const CHART_MATCHES = 2
const lastName = (name) => name.split(' ').slice(-1)[0]

/**
 * Retired players whose scoring-by-age curve looked like this player's, and (for a current player)
 * what those players did afterwards. A rough guide from points alone, not a forecast.
 */
export default function Comparables({ playerId }) {
  const [result, setResult] = useState({ id: null, data: null })

  useEffect(() => {
    let ignore = false
    fetch(`/api/players/${playerId}/comparables`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setResult({ id: playerId, data }))
      .catch(() => !ignore && setResult({ id: playerId, data: null }))
    return () => { ignore = true }
  }, [playerId])

  const data = result.id === playerId ? result.data : null
  if (!data) return null
  const { player, matches, projection } = data

  const series = [
    { id: 'me', name: lastName(player.name), slot: 1, points: data.curve.map((c) => ({ x: c.age, y: c.value })) },
    ...matches.slice(0, CHART_MATCHES).map((m, i) => ({
      id: m.player_id, name: lastName(m.name), slot: i + 2, points: m.curve.map((c) => ({ x: c.age, y: c.value })),
    })),
  ]
  const top = Math.ceil(Math.max(...series.flatMap((s) => s.points.map((p) => p.y)), 1))
  const yDomain = { min: 0, max: top, ticks: Array.from({ length: top + 1 }, (_, i) => i) }

  return (
    <section>
      <h2>Career comparables</h2>
      <p className="sub">
        Retired {player.position === 'D' ? 'defensemen' : 'forwards'} whose scoring at the same ages looked most like
        {' '}{player.name}'s. Each season is points per game relative to the league's average for that year (1.0 is a
        typical regular), so eras are comparable. Only seasons with {data.min_gp}+ games count, and this ignores
        ice time, injuries and everything but points.
      </p>
      {matches.length === 0 ? (
        <p className="status">
          {data.seasons < 2 ? 'Needs at least two seasons with 20+ games to find comparables.' : 'No close matches found.'}
        </p>
      ) : (
        <>
          {data.seasons < 4 && <p className="sub">Only {data.seasons} qualifying seasons so far, so these matches are loose.</p>}
          {projection && (
            <p className="sub">
              <strong>What came next:</strong> the {projection.matches} closest matches scored a median of{' '}
              {projection.median} more points after this age (middle half {projection.low}–{projection.high}), scaled
              to today's scoring level. Players who retired soon after count as low totals, so this is a spread of
              outcomes, not a prediction.
            </p>
          )}
          <CompareChart
            title={`Scoring by age: ${player.name} and closest matches`}
            series={series}
            xLabel="Age"
            yLabel="points per game vs. league average (1.0 = typical regular)"
            yDomain={yDomain}
            yFmt={(v) => v.toFixed(1)}
          />
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="left">Player</th><th className="left">Pos</th><th>Match</th><th>Seasons compared</th>
                  <th className="left">Career</th><th>GP</th><th>P</th><th>Peak age</th>
                  {player.active && <th title="Points after this player's current age, scaled to today's scoring level">Points after</th>}
                </tr>
              </thead>
              <tbody>
                {matches.map((m) => (
                  <tr key={m.player_id}>
                    <td className="left"><Link to={`/player/${m.player_id}`}>{m.name}</Link>{m.hall_of_fame ? ' · HHOF' : ''}</td>
                    <td className="left">{m.position}</td>
                    <td className="accent">{m.similarity}</td>
                    <td>{m.seasons_compared}</td>
                    <td className="left">{seasonLabel(m.first_season).slice(0, 4)}–{seasonLabel(m.last_season).slice(0, 4)}</td>
                    <td>{m.games_played}</td><td>{m.points}</td><td>{m.peak_age}</td>
                    {player.active && <td>{m.after_points}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
