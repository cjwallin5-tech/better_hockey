import { Link } from 'react-router-dom'
import { useAuth } from '../auth.js'
import { useFantasy } from '../fantasy.js'
import Icon from './Icon.jsx'

/** A toggle that adds a player ({ id, kind: 'skater' | 'goalie', name }) to your fantasy team. Fantasy needs an account, so signed out it links to log in. */
export default function FantasyStar({ player }) {
  const { user, ready } = useAuth()
  const { hasPlayer, togglePlayer } = useFantasy()
  if (ready && !user) {
    return <Link className="star" to="/account" title="Log in to build a fantasy team"><Icon name="star" /> <span>Add to team</span></Link>
  }
  const on = hasPlayer(player.id)
  return (
    <button
      className={`star ${on ? 'on' : ''}`}
      aria-pressed={on}
      aria-label={on ? `Remove ${player.name} from your fantasy team` : `Add ${player.name} to your fantasy team`}
      title={on ? 'On your fantasy team' : 'Add to your fantasy team'}
      onClick={() => togglePlayer(player)}
    >
      <Icon name="star" filled={on} /> <span>{on ? 'On my team' : 'Add to team'}</span>
    </button>
  )
}
