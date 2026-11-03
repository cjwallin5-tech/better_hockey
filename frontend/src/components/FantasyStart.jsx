import { Link } from 'react-router-dom'
import { Skeleton } from './Skeleton.jsx'
import TeamMark from './TeamMark.jsx'

const TOP = 6

/**
 * What the roster tab shows before any player is added: the players worth the most over the rest of the season (the same
 * values the rest of the page uses), each one click from the roster, so a new visitor has something real to start from.
 * `values` is the Map from value.js (null while loading); `info` maps a player id to { name, team, position, kind }.
 */
export default function FantasyStart({ values, info, onAdd }) {
  const top = values
    ? [...values.values()].filter((v) => info.has(v.id)).sort((a, b) => a.overallRank - b.overallRank).slice(0, TOP)
    : null
  return (
    <section className="card start">
      <div className="eyebrow">Your team starts here</div>
      <p className="start-lead">Search for a player above, or start from the ones worth the most over the rest of the season.</p>
      {!top ? <Skeleton rows={TOP} /> : (
        <ul className="start-list">
          {top.map((v) => {
            const p = info.get(v.id)
            return (
              <li key={v.id}>
                <TeamMark abbrev={(p.team ?? '').split(',').pop()} size={24} />
                <span className="start-name">
                  <Link to={p.kind === 'goalie' ? `/goalie/${v.id}` : `/player/${v.id}`}>{p.name}</Link>
                  <small>{p.team} · {p.position}</small>
                </span>
                <strong className="start-value" title="Worth over the rest of the season, above the best free player at the position">{v.value.toFixed(1)}</strong>
                <button type="button" className="start-add" onClick={() => onAdd(v.id)}>Add</button>
              </li>
            )
          })}
        </ul>
      )}
      <p className="start-foot">
        Not sure who to pick? <Link to="/fantasy?tab=mock">Try a mock draft</Link> or <Link to="/fantasy?tab=values">browse every player's value</Link>.
      </p>
    </section>
  )
}
