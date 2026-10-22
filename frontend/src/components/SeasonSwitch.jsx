import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { seasonLabel } from '../career.js'

/**
 * Which stretch of history a leaderboard covers: a season picker, plus a link to the all-time leaders.
 * kind: 'skater' or 'goalie'. active: 'season' on the Skaters/Goalies pages, 'alltime' on the all-time pages.
 * value: the picked past season's id, or null for the current season. onChange(id) gets null when the current season is picked.
 */
export default function SeasonSwitch({ kind, active = 'season', value = null, onChange }) {
  const [seasons, setSeasons] = useState(null) // { current, ids }
  useEffect(() => {
    let ignore = false
    fetch('/api/seasons')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => !ignore && d && setSeasons({ current: d.current, ids: kind === 'goalie' ? d.goalies : d.skaters }))
      .catch(() => {})
    return () => { ignore = true }
  }, [kind])

  const board = kind === 'goalie' ? '/goalies' : '/skaters'
  const alltime = active === 'alltime'
    ? <button type="button" className="on" aria-current="page">All-time</button>
    : <Link className="tab-link" to={kind === 'goalie' ? '/alltime/goalies' : '/alltime/skaters'}>All-time</Link>

  if (active === 'alltime') {
    return (
      <nav className="tabs season-switch" aria-label="Season">
        <Link className="tab-link" to={board}>{seasons ? seasonLabel(seasons.current) : 'This season'}</Link>
        {alltime}
      </nav>
    )
  }
  return (
    <nav className="tabs season-switch" aria-label="Season">
      <label className="season-pick">
        <span>Season</span>
        <select value={value ?? seasons?.current ?? ''} disabled={!seasons} onChange={(e) => {
          const id = Number(e.target.value)
          onChange?.(id === seasons.current ? null : id)
        }}>
          {seasons
            ? seasons.ids.map((id) => <option key={id} value={id}>{seasonLabel(id)}{id === seasons.current ? ' (current)' : ''}</option>)
            : <option value="">Loading…</option>}
        </select>
      </label>
      {alltime}
    </nav>
  )
}
