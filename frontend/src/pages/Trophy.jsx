import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { seasonLabel } from '../career.js'
import { describe } from '../glossary.js'

const COLUMN_LABEL = { games_played: 'GP', goals: 'G', assists: 'A', points: 'P' }
// The stat that decides the award is emphasised.
const DECIDING = { 15: 'goals', 16: 'points' }

/** Every winner of one trophy, newest season first. The scoring awards also show the winner's season totals. */
export default function Trophy() {
  const { id } = useParams()
  const [result, setResult] = useState({ id: null, data: null, error: null })

  useEffect(() => {
    let ignore = false
    fetch(`/api/trophy/${id}`)
      .then((r) => {
        if (r.status === 404) throw new Error('Trophy not found')
        if (!r.ok) throw new Error(`The NHL records site isn't answering (${r.status})`)
        return r.json()
      })
      .then((data) => !ignore && setResult({ id, data, error: null }))
      .catch((error) => !ignore && setResult({ id, data: null, error: error.message }))
    return () => { ignore = true }
  }, [id])

  const { data, error } = result.id === id ? result : { data: null, error: null }
  const back = <Link to="/trophy" className="back">← All trophies</Link>
  if (error) return <main>{back}<p className="status">{error}</p></main>
  if (!data) return <main>{back}<p className="status">Loading…</p></main>

  const columns = data.stat_columns ?? []
  const deciding = DECIDING[data.id]
  return (
    <main>
      {back}
      <header>
        <h1>{data.name}</h1>
        {data.description && <p>{data.description}. {data.winners.length} winners since {seasonLabel(data.winners[data.winners.length - 1]?.season_id)}.</p>}
      </header>
      <div className="table-wrap">
        <table className="trophy-table">
          <thead>
            <tr>
              <th className="left">Season</th>
              <th className="left">{data.is_team ? 'Team' : 'Winner'}</th>
              {!data.is_team && <th className="left" title={describe('Team')}>Team</th>}
              {columns.map((c) => <th key={c} title={describe(COLUMN_LABEL[c])}>{COLUMN_LABEL[c]}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.winners.map((w) => (
              <tr key={`${w.season_id}-${w.player_id ?? w.name}`}>
                <td className="left">{seasonLabel(w.season_id)}</td>
                <td className="left">{w.player_id ? <Link to={`/player/${w.player_id}`}>{w.name}</Link> : w.name}</td>
                {!data.is_team && <td className="left">{w.team ?? '–'}</td>}
                {columns.map((c) => (
                  <td key={c} className={c === deciding ? 'accent' : ''}>{w.stats?.[c] ?? '–'}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  )
}
