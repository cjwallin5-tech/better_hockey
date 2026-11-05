import { useEffect, useState } from 'react'
import { teamColor } from '../teamColors.js'

const initials = (name) => (name ?? '').split(/\s+/).filter(Boolean).map((w) => w[0]).slice(0, 2).join('').toUpperCase()

// The NHL's picture host keeps one folder per season ("20262027"); the "latest" folder only serves a grey silhouette. One shared
// request finds the current season.
let season = null
const currentSeason = () => {
  if (!season) {
    season = fetch('/api/meta').then((r) => (r.ok ? r.json() : null)).then((m) => m?.season_id ?? null).catch(() => { season = null; return null })
  }
  return season
}

/**
 * A small round headshot ringed in the team's colour, built straight from the season, team and player id (no per-player request).
 * Lazy, since a table can hold hundreds; initials stand in until the season is known and when there is no picture. Pass `season` (and
 * that season's `team`) for a player who is not on a current roster, such as a retired player on the all-time board.
 */
export default function Avatar({ playerId, team, name, size = 32, season: fixedSeason }) {
  const [currentId, setCurrentId] = useState(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    if (fixedSeason) return undefined
    let ignore = false
    currentSeason().then((s) => !ignore && setCurrentId(s))
    return () => { ignore = true }
  }, [fixedSeason])
  const seasonId = fixedSeason ?? currentId
  const current = (team ?? '').split(',').filter(Boolean).pop()
  const style = { '--team': teamColor(current), '--s': `${size}px` }
  if (!current || !seasonId || failed) return <span className="avatar blank" style={style} aria-hidden="true">{initials(name)}</span>
  return (
    <img
      className="avatar" style={style} alt="" width={size} height={size} loading="lazy" decoding="async"
      src={`https://assets.nhle.com/mugs/nhl/${seasonId}/${current}/${playerId}.png`} onError={() => setFailed(true)}
    />
  )
}
