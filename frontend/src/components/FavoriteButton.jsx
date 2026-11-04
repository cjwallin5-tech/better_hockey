import { Link } from 'react-router-dom'
import { useFavoriteTeam } from '../favorite.js'

/** "Make this my team" on a team page; links to the My team page once it is the favorite. My team is saved to an account, so signed out it asks you to log in. */
export default function FavoriteButton({ abbrev }) {
  const { favorite, setFavorite, signedIn, ready } = useFavoriteTeam()
  if (ready && !signedIn) return <Link className="link-button" to="/account" title="My team is saved to your account">Log in to make this my team</Link>
  if (favorite === abbrev) {
    return (
      <>
        <Link to="/my-team">Your team: game by game →</Link>{' '}
        <button className="link-button" onClick={() => setFavorite(null)}>Not my team</button>
      </>
    )
  }
  return <button className="link-button" onClick={() => setFavorite(abbrev)}>Make this my team</button>
}
