import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fmt1, fmtToi } from '../format.js'
import { describe } from '../glossary.js'

export default function Similar({ playerId }) {
  const [result, setResult] = useState({ id: null, data: null, error: null })

  useEffect(() => {
    fetch(`/api/skaters/${playerId}/similar`)
      .then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`)
        return r.json()
      })
      .then((data) => setResult({ id: playerId, data, error: null }))
      .catch((error) => setResult({ id: playerId, data: null, error: error.message }))
  }, [playerId])

  const { data, error } = result.id === playerId ? result : { data: null, error: null }
  if (error) return null
  if (!data) return null

  return (
    <section>
      <h2>Players like this</h2>
      <p className="sub">
        Closest playing styles this season among {data.peer_count} skaters in the same role with at
        least {data.min_gp} GP, judged on {data.features.join(', ')}. Early in the season these
        matches are noisy.
      </p>
      {data.matches.length === 0 ? (
        <p className="status">Not enough data to find similar players yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="left">Player</th><th className="left" title={describe('Team')}>Team</th><th className="left" title={describe('Pos')}>Pos</th>
                <th title={describe('Style match')}>Style match</th><th title={describe('GP')}>GP</th><th title={describe('G')}>G</th><th title={describe('P')}>P</th><th title={describe('TOI')}>TOI</th>
                <th title={describe('Hits/60')}>Hits/60</th><th title={describe('BLK/60')}>BLK/60</th><th className="left">What you share</th>
              </tr>
            </thead>
            <tbody>
              {data.matches.map((m) => (
                <tr key={m.player_id}>
                  <td className="left"><Link to={`/player/${m.player_id}`}>{m.name}</Link></td>
                  <td className="left">{m.team}</td>
                  <td className="left">{m.position}</td>
                  <td className="accent">{m.similarity}</td>
                  <td>{m.games_played}</td><td>{m.goals}</td><td>{m.points}</td>
                  <td>{fmtToi(m.toi_per_game_sec)}</td>
                  <td>{fmt1(m.hits_per60)}</td><td>{fmt1(m.blocks_per60)}</td>
                  <td className="left shared">{m.shared.length ? m.shared.join(' · ') : '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
