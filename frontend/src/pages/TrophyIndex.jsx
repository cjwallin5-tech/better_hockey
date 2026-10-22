import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { seasonLabel } from '../career.js'

/** Every NHL trophy by kind, each linking to its list of winners by season. */
export default function TrophyIndex() {
  const [state, setState] = useState({ data: null, error: null })
  useEffect(() => {
    let ignore = false
    fetch('/api/trophy-summary')
      .then((r) => {
        if (!r.ok) throw new Error(`The NHL records site isn't answering (${r.status})`)
        return r.json()
      })
      .then((data) => !ignore && setState({ data, error: null }))
      .catch((error) => !ignore && setState({ data: null, error: error.message }))
    return () => { ignore = true }
  }, [])

  if (state.error) return <main><p className="status">{state.error}</p></main>
  if (!state.data) return <main><p className="status">Loading…</p></main>

  return (
    <main>
      <header>
        <h1>Trophy winners</h1>
        <p>Every NHL trophy with its winners by season. Open one to see the full list. For the Art Ross and Rocket Richard, the winner's season totals are shown too.</p>
      </header>
      {state.data.groups.map((group) => (
        <section key={group.title}>
          <h2>{group.title}</h2>
          <div className="table-wrap">
            <table className="trophy-index">
              <thead>
                <tr>
                  <th className="left">Trophy</th>
                  <th className="left">Awarded for</th>
                  <th className="left">Latest winner</th>
                  <th className="left">Since</th>
                </tr>
              </thead>
              <tbody>
                {group.trophies.map((t) => (
                  <tr key={t.id}>
                    <td className="left"><Link to={`/trophy/${t.id}`}>{t.name}</Link></td>
                    <td className="left">{t.description ?? '–'}</td>
                    <td className="left">
                      {t.latest ? (
                        <>
                          {t.latest.player_id ? <Link to={`/player/${t.latest.player_id}`}>{t.latest.name}</Link> : t.latest.name}
                          {' '}<span className="muted">{seasonLabel(t.latest.season_id)}</span>
                        </>
                      ) : '–'}
                    </td>
                    <td className="left">{t.first_season ? seasonLabel(t.first_season) : '–'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </main>
  )
}
