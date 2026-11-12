import { useEffect, useState } from 'react'
import { getJson } from '../lists.js'
import { medalText, resultLabel, tournamentName } from '../international.js'
import Medal from './Medal.jsx'

const num = (v) => (v == null ? '–' : v)

/** A player's national-team tournaments (Olympics, World Championship, World Cup / Canada Cup, 4 Nations, World Juniors) with the medal
 *  his team won. Nothing when he has never played in one. */
export default function InternationalMedals({ playerId }) {
  const [state, setState] = useState({ id: null, data: null })
  useEffect(() => {
    let ignore = false
    getJson(`/api/players/${playerId}/international`)
      .then((data) => !ignore && setState({ id: playerId, data }))
      .catch(() => !ignore && setState({ id: playerId, data: null }))
    return () => { ignore = true }
  }, [playerId])
  const d = state.id === playerId ? state.data : null
  if (!d || (d.appearances.length === 0 && d.honors.length === 0)) return null

  const total = medalText(d.medals)
  return (
    <section>
      <h2>International play</h2>
      <p className="sub">
        {total
          ? <>Medals with the national team: {['gold', 'silver', 'bronze'].filter((m) => d.medals[m] > 0).map((m) => <span key={m} className="intl-count"><Medal medal={m} /> {d.medals[m]} {m}</span>)}</>
          : 'No medals yet.'}
      </p>
      {d.triple_gold && (
        <p className="intl-club">
          <span className="badge">Triple Gold Club</span> Stanley Cup {d.triple_gold.cup}, Olympic gold {d.triple_gold.olympics} and World Championship gold {d.triple_gold.worlds}:
          completed in {d.triple_gold.completed}.
          {d.triple_gold.source === 'official' && <span className="muted"> From the IIHF's roll: the table below is missing a tournament row the NHL's data leaves out.</span>}
        </p>
      )}
      {d.honors.length > 0 && (
        <div className="intl-honors">
          <h3>Tournament awards</h3>
          <ul>
            {d.honors.map((h) => (
              <li key={`${h.tournament}-${h.year}-${h.award}`}>
                <span className="intl-honor-year">{h.year}</span> {h.award_label} <span className="muted">{tournamentName(h)}, {h.country}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {d.appearances.length > 0 && (
      <div className="table-wrap">
        <table className="awards-table intl-table">
          <thead>
            <tr><th className="left">Year</th><th className="left">Tournament</th><th className="left">Team</th><th className="left">Result</th><th>GP</th><th>G</th><th>A</th><th>P</th></tr>
          </thead>
          <tbody>
            {d.appearances.map((a) => (
              <tr key={`${a.tournament}-${a.year}`} className={a.tier > 1 ? 'minor' : ''}>
                <td className="left">{a.year}</td>
                <td className="left">{tournamentName(a)}</td>
                <td className="left">{a.country}</td>
                <td className="left">{a.medal ? <span className="intl-result"><Medal medal={a.medal} /> {resultLabel(a)}</span> : <span className="muted">Played</span>}</td>
                <td>{num(a.games)}</td><td>{num(a.goals)}</td><td>{num(a.assists)}</td><td>{num(a.points)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
    </section>
  )
}
