import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { seasonLabel } from '../career.js'

const ALL_TIME = 'alltime'

/**
 * Which stretch of history a leaderboard covers, as one dropdown: the current season, All-time (second), then the past seasons.
 * It sits in the same place on the season pages and the all-time pages; picking an entry opens that view.
 * kind: 'skater' or 'goalie'. active: 'season' on the Skaters/Goalies pages, 'alltime' on the all-time pages.
 * value: the picked past season's id, or null for the current season. onChange(id) gets null when the current season is picked.
 */
export default function SeasonSwitch({ kind, active = 'season', value = null, onChange }) {
  const [seasons, setSeasons] = useState(null) // { current, ids }
  const navigate = useNavigate()
  useEffect(() => {
    let ignore = false
    fetch('/api/seasons')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => !ignore && d && setSeasons({ current: d.current, ids: kind === 'goalie' ? d.goalies : d.skaters }))
      .catch(() => {})
    return () => { ignore = true }
  }, [kind])

  const board = kind === 'goalie' ? '/goalies' : '/skaters'
  const current = seasons?.current
  const selected = active === 'alltime' ? ALL_TIME : (value ?? current ?? '')

  const pick = (e) => {
    if (e.target.value === ALL_TIME) {
      if (active !== 'alltime') navigate(kind === 'goalie' ? '/alltime/goalies' : '/alltime/skaters')
      return
    }
    const id = Number(e.target.value)
    if (active === 'season') onChange?.(id === current ? null : id)
    else navigate(id === current ? board : `${board}?season=${id}`)
  }

  const ids = seasons?.ids ?? []
  const label = (id) => `${seasonLabel(id)}${id === current ? ' (current)' : ''}`
  return (
    <nav className="season-switch" aria-label="Season">
      <label className="season-select">
        <select aria-label="Season or all-time" value={selected} disabled={!seasons} onChange={pick}>
          {seasons ? (
            <>
              {ids.filter((id) => id === current).map((id) => <option key={id} value={id}>{label(id)}</option>)}
              <option value={ALL_TIME}>All-time</option>
              {ids.filter((id) => id !== current).map((id) => <option key={id} value={id}>{label(id)}</option>)}
            </>
          ) : <option value="">Loading…</option>}
        </select>
      </label>
    </nav>
  )
}
