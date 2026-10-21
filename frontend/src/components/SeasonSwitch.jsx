import { Link } from 'react-router-dom'

const label = (id) => `${String(id).slice(0, 4)}–${String(id).slice(6)}`

/**
 * Switches a leaderboard between the current season and all-time, so neither needs its own menu entry.
 * active: which one this page is ('season' or 'alltime'). Past seasons can be added here once their stats are stored.
 */
export default function SeasonSwitch({ seasonId, kind, active = 'season' }) {
  const season = active === 'season'
    ? <button type="button" className="on" aria-current="page">{seasonId != null ? label(seasonId) : 'This season'}</button>
    : <Link className="tab-link" to={kind === 'goalie' ? '/goalies' : '/skaters'}>{seasonId != null ? label(seasonId) : 'This season'}</Link>
  const alltime = active === 'alltime'
    ? <button type="button" className="on" aria-current="page">All-time</button>
    : <Link className="tab-link" to={kind === 'goalie' ? '/alltime/goalies' : '/alltime/skaters'}>All-time</Link>
  return <nav className="tabs season-switch" aria-label="Season">{season}{alltime}</nav>
}
