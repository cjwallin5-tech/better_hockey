import Info from './Info.jsx'
import { useByIds } from '../fantasyData.js'

const n0 = (v) => Math.round(v)

/** The gap between the projected finish and the current pace, short enough to sit under the number. */
function projectionGap(p) {
  const pace = Math.round(p.point_pace)
  const gap = Math.round(p.final_points) - pace
  return Math.abs(gap) < 3 ? `About the current ${pace}-point pace` : `${Math.abs(gap)} ${gap > 0 ? 'above' : 'below'} the current ${pace}-point pace`
}

/** Projected finish for one skater: points, goals and assists with an 80% range for the points. Nothing for goalies. */
export default function Projection({ playerId }) {
  const p = useByIds('/api/projections', [playerId])?.rows?.[0]
  if (!p) return null

  return (
    <section className="card projection">
      <div className="eyebrow">
        Projected finish
        <Info label="Projected finish">
          The season so far is pulled toward {p.has_record ? "the player's last two seasons" : 'the average for the position, since there is no recent record'}, with some credit
          for the quality of their shots, then carried over the games left. The range covers 80% of likely outcomes. Injuries are not predicted.
        </Info>
      </div>
      <div className="proj-main">
        <strong>{n0(p.final_points)}</strong><span>points</span>
        <small>80% range {n0(p.low_points)} to {n0(p.high_points)}</small>
      </div>
      <dl className="proj-row">
        <div><dd>{n0(p.final_goals)}</dd><dt>goals</dt></div>
        <div><dd>{n0(p.final_assists)}</dd><dt>assists</dt></div>
        <div><dd>{n0(p.expected_games)}</dd><dt>games expected</dt></div>
      </dl>
      <p className="sub">{projectionGap(p)}</p>
    </section>
  )
}
