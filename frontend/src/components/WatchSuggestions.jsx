import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import TeamMark from './TeamMark.jsx'
import { getJson } from '../lists.js'

const SHOWN = 5

/** Players on a point streak right now, as a short list of who is worth following. With `onFollow` each one has a Follow button. */
export default function WatchSuggestions({ onFollow, exclude }) {
  const [hot, setHot] = useState(null)
  useEffect(() => {
    let ignore = false
    getJson('/api/home').then((d) => !ignore && setHot(d.hot)).catch(() => !ignore && setHot([]))
    return () => { ignore = true }
  }, [])
  const rows = (hot ?? []).filter((p) => !exclude?.has(String(p.player_id))).slice(0, SHOWN)
  if (rows.length === 0) return null
  return (
    <>
      <div className="eyebrow">On a point streak right now</div>
      <ul className="start-list">
        {rows.map((p) => (
          <li key={p.player_id}>
            <TeamMark abbrev={p.team} size={24} />
            <span className="start-name">
              <Link to={`/player/${p.player_id}`}>{p.name}</Link>
              <small>{p.team} · {p.position}</small>
            </span>
            <strong className="start-value">{p.streak}<small> games</small></strong>
            {onFollow ? <button type="button" className="start-add" onClick={() => onFollow(p)}>Follow</button> : <span />}
          </li>
        ))}
      </ul>
    </>
  )
}
