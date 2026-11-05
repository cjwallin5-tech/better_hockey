import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { goalieProjectionFigures, goalieProjectionNote, goalieRange } from '../goalieProjection.js'

/** Projected finish for one goalie: wins as the headline, with saves, goals against, shutouts and starts left. Nothing when
 *  the goalie has no projection (no games yet, or no team game left to start). */
export default function GoalieProjection({ playerId }) {
  const [state, setState] = useState({ id: null, row: null })
  useEffect(() => {
    let ignore = false
    fetch(`/api/projections/goalies?ids=${playerId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => !ignore && setState({ id: playerId, row: d?.rows?.[0] ?? null }))
      .catch(() => !ignore && setState({ id: playerId, row: null }))
    return () => { ignore = true }
  }, [playerId])
  const p = state.id === playerId ? state.row : null
  if (!p) return null

  return (
    <section className="card projection goalie-projection">
      <div className="eyebrow">Projected finish</div>
      <div className="proj-main">
        <strong>{Math.round(p.final_wins)}</strong><span>wins</span>
        <small>80% range {goalieRange(p, 'wins')}</small>
      </div>
      <dl className="proj-row">
        {goalieProjectionFigures(p).map((f) => (
          <div key={f.label}><dd>{f.value}</dd><dt>{f.label}</dt></div>
        ))}
      </dl>
      <p className="sub">
        {goalieProjectionNote(p)} The starts come from how his team has been using its goalies, and the range covers luck and
        uncertainty in the start count, not injuries, trades or a backup taking over. <Link to="/projections?kind=goalies">See every goalie's projection →</Link>
      </p>
    </section>
  )
}
