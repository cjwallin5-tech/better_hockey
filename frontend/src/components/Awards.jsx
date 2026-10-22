import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { seasonLabel } from '../career.js'
import { fetchBio } from '../playerBio.js'
import { trophyIds, trophyKey } from '../trophies.js'

/** Every award a player has won, with how many times and in which seasons. Nothing when they have none. */
export default function Awards({ playerId }) {
  const [bio, setBio] = useState(null)
  const [ids, setIds] = useState({})
  useEffect(() => {
    let ignore = false
    fetchBio(playerId).then((b) => !ignore && setBio(b))
    trophyIds().then((i) => !ignore && setIds(i))
    return () => { ignore = true }
  }, [playerId])
  if (!bio) return null
  const awards = [...bio.awards].sort((a, b) => Math.max(...b.seasons) - Math.max(...a.seasons))
  if (awards.length === 0 && !bio.in_hhof) return null
  return (
    <section>
      <h2>Awards</h2>
      <div className="table-wrap">
        <table className="awards-table">
          <thead>
            <tr><th className="left">Award</th><th>Won</th><th className="left">Seasons</th></tr>
          </thead>
          <tbody>
            {bio.in_hhof ? (
              <tr><td className="left">Hockey Hall of Fame</td><td>–</td><td className="left muted">Inducted</td></tr>
            ) : null}
            {awards.map((a) => (
              <tr key={a.name}>
                <td className="left">{ids[trophyKey(a.name)] ? <Link to={`/trophy/${ids[trophyKey(a.name)]}`}>{a.name}</Link> : a.name}</td>
                <td>{a.seasons.length}</td>
                <td className="left">{[...a.seasons].sort().map(seasonLabel).join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
