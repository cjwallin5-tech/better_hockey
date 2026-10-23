import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Line, ProspectName, draftText } from './ProspectBits.jsx'

/** A team's top prospects this season by points per game (or save percentage for goalies), with a link to all of them. */
export default function TeamProspects({ abbrev }) {
  const [state, setState] = useState({ abbrev: null, rows: null })
  useEffect(() => {
    let ignore = false
    fetch(`/api/prospects?team=${abbrev}&min_games=1&limit=8`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => !ignore && setState({ abbrev, rows: d?.rows ?? [] }))
      .catch(() => !ignore && setState({ abbrev, rows: [] }))
    return () => { ignore = true }
  }, [abbrev])
  const rows = state.abbrev === abbrev ? state.rows : null
  if (!rows || rows.length === 0) return null

  return (
    <section>
      <h2>Prospects</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th className="left">Prospect</th><th className="left">Pos</th><th>Age</th><th className="left">Playing for</th><th className="left">This season</th><th className="left">Drafted</th></tr></thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.player_id}>
                <td className="left"><ProspectName p={p} /></td><td className="left">{p.position}</td><td>{p.age ?? '–'}</td>
                <td className="left">{p.league ?? '–'}</td><td className="left"><Line p={p} /></td><td className="left">{draftText(p.draft)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="sub">Sorted by points per game. <Link to={`/prospects?team=${abbrev}`}>All of {abbrev}'s prospects →</Link></p>
    </section>
  )
}
