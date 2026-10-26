import { Link } from 'react-router-dom'
import { useFavoriteTeam } from '../favorite.js'

/** "Make this my team" on a team page; links to the My team page once it is the favorite. */
export default function FavoriteButton({ abbrev }) {
  const { favorite, setFavorite } = useFavoriteTeam()
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
