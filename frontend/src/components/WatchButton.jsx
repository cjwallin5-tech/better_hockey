import { Link } from 'react-router-dom'
import { useWatchlist } from '../watchlist.js'
import Icon from './Icon.jsx'

/** Follows a player or team in the daily email. kind: 'player' | 'team'; refId: player id or team abbreviation. */
export default function WatchButton({ kind, refId, name }) {
  const { signedIn, status, has, toggle, error } = useWatchlist()
  if (!signedIn) {
    return <Link className="star" to="/account" title="Log in to follow this in your daily email"><Icon name="eye" /> <span>Watch</span></Link>
  }
  const on = has(kind, refId)
  return (
    <>
      <button
        className={`star ${on ? 'on' : ''}`}
        aria-pressed={on}
        disabled={status === 'loading'}
        aria-label={on ? `Stop watching ${name}` : `Watch ${name}`}
        title={on ? 'On your watchlist' : 'Add to your watchlist (daily email)'}
        onClick={() => toggle(kind, refId, name)}
      >
        <Icon name="eye" filled={on} /> <span>{on ? 'Watching' : 'Watch'}</span>
      </button>
      {error && <span className="muted" role="alert"> {error}</span>}
    </>
  )
}
