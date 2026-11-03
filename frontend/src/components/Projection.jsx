import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const n0 = (v) => Math.round(v)

/** The one-line story behind a projection: where the finish sits against the current pace, and why. */
export function projectionNote(p) {
  const pace = Math.round(p.point_pace)
  const gap = Math.round(p.final_points) - pace
  const against = Math.abs(gap) < 3
    ? `about the current ${pace}-point pace`
    : `${Math.abs(gap)} points ${gap > 0 ? 'above' : 'below'} the current ${pace}-point pace`
  const basis = p.has_record
    ? "pulled toward the player's last two seasons"
    : 'pulled toward the average for the position, since there is no recent record'
  return `${against}: the season so far is ${basis}, with some credit for the quality of their shots.`
}

/** Projected finish for one skater: points, goals and assists with an 80% range for the points. Nothing for goalies. */
export default function Projection({ playerId }) {
  const [state, setState] = useState({ id: null, row: null })
  useEffect(() => {
    let ignore = false
    fetch(`/api/projections?ids=${playerId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => !ignore && setState({ id: playerId, row: d?.rows?.[0] ?? null }))
      .catch(() => !ignore && setState({ id: playerId, row: null }))
    return () => { ignore = true }
  }, [playerId])
  const p = state.id === playerId ? state.row : null
  if (!p) return null

  return (
    <section className="card projection">
      <div className="eyebrow">Projected finish</div>
      <div className="proj-main">
        <strong>{n0(p.final_points)}</strong><span>points</span>
        <small>80% range {n0(p.low_points)} to {n0(p.high_points)}</small>
      </div>
      <dl className="proj-row">
        <div><dd>{n0(p.final_goals)}</dd><dt>goals</dt></div>
        <div><dd>{n0(p.final_assists)}</dd><dt>assists</dt></div>
        <div><dd>{n0(p.expected_games)}</dd><dt>games left</dt></div>
      </dl>
      <p className="sub">
        {projectionNote(p)} Injuries are not predicted. <Link to="/projections">See every skater's projection →</Link>
      </p>
    </section>
  )
}
