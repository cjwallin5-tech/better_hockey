import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { describe } from '../glossary.js'

const STAT = { points: 'Points', goals: 'Goals', gsaa: 'GSAA' }
const fmtValue = (stat, v) => (stat === 'gsaa' ? `${v > 0 ? '+' : ''}${v.toFixed(1)}` : v)

export default function TrophyRaces() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    fetch('/api/trophy-races')
      .then((r) => { if (!r.ok) throw new Error(`API returned ${r.status}`); return r.json() })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <main><p className="status">{error}</p></main>
  if (!data) return <main><p className="status">Loading…</p></main>

  return (
    <main>
      <header>
        <h1>Trophy races</h1>
        <p>
          Who is in the running for each stat-driven award: the top {data.size} (ties included) in the stat that
          decides it. Voted awards like the Hart and Selke aren't covered. Early in the season this changes fast.
        </p>
      </header>
      {data.races.map((race) => (
        <section key={race.trophy}>
          <h2>{race.trophy}</h2>
          <p className="sub">{race.basis[0].toUpperCase() + race.basis.slice(1)}.</p>
          {race.contenders.length === 0 ? <p className="status">No contenders yet.</p> : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>#</th><th className="left">Player</th><th className="left" title={describe('Team')}>Team</th><th title={describe('GP')}>GP</th><th>{STAT[race.stat]}</th></tr></thead>
                <tbody>
                  {race.contenders.map((c) => (
                    <tr key={c.player_id}>
                      <td>{c.rank}</td>
                      <td className="left"><Link to={`/${race.stat === 'gsaa' ? 'goalie' : 'player'}/${c.player_id}`}>{c.name}</Link></td>
                      <td className="left">{c.team}</td><td>{c.games_played}</td>
                      <td className="accent">{fmtValue(race.stat, c.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ))}
    </main>
  )
}
