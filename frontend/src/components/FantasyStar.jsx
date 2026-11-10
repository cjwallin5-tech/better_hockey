import { Link } from 'react-router-dom'
import { useAuth } from '../auth.js'
import { useRoster } from '../roster.js'
import Icon from './Icon.jsx'

/** A toggle that adds a player ({ id, kind: 'skater' | 'goalie', name }) to your fantasy team: your roster in the active league when it has one, else your personal roster. Fantasy needs an account, so signed out it links to log in. */
export default function FantasyStar({ player }) {
  const { user, ready } = useAuth()
  const { hasPlayer, togglePlayer, source } = useRoster()
  if (ready && !user) {
    return <Link className="star" to="/account" title="Log in to build a fantasy team"><Icon name="star" /> <span>Add to team</span></Link>
  }
  const on = hasPlayer(player.id)
  const team = source.kind === 'league' ? `your ${source.name} team` : 'your fantasy team'
  return (
    <button
      className={`star ${on ? 'on' : ''}`}
      aria-pressed={on}
      aria-label={on ? `Remove ${player.name} from ${team}` : `Add ${player.name} to ${team}`}
      title={on ? `On ${team}` : `Add to ${team}`}
      disabled={source.kind === 'loading'}
      onClick={() => togglePlayer(player)}
    >
      <Icon name="star" filled={on} /> <span>{on ? 'On my team' : 'Add to team'}</span>
    </button>
  )
}
