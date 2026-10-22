import { useEffect, useState } from 'react'
import { fetchBio } from '../playerBio.js'

function age(birthDate) {
  const b = new Date(`${birthDate}T00:00:00`)
  const now = new Date()
  let a = now.getFullYear() - b.getFullYear()
  if (now < new Date(now.getFullYear(), b.getMonth(), b.getDate())) a--
  return a
}

/** Jersey number, handedness, size, birthplace, draft and awards: the facts NHL.com puts at the top of a player page. */
export default function PlayerBio({ playerId }) {
  const [bio, setBio] = useState(null)
  useEffect(() => {
    let ignore = false
    fetchBio(playerId).then((b) => !ignore && setBio(b))
    return () => { ignore = true }
  }, [playerId])
  if (!bio) return null
  const goalie = bio.is_goalie
  const facts = [
    bio.sweater != null && `#${bio.sweater}`,
    bio.shoots_catches && `${goalie ? 'Catches' : 'Shoots'} ${bio.shoots_catches}`,
    bio.height_in && `${Math.floor(bio.height_in / 12)}'${bio.height_in % 12}"`,
    bio.weight_lb && `${bio.weight_lb} lb`,
  ].filter(Boolean)
  return (
    <div className="player-bio">
      {facts.length > 0 && <p className="bio-line">{facts.join(' · ')}</p>}
      {bio.birth_date && (
        <p className="bio-line muted">
          Born {new Date(`${bio.birth_date}T00:00:00`).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}
          {' '}(age {age(bio.birth_date)}) in {[bio.birth_city, bio.birth_state, bio.birth_country].filter(Boolean).join(', ')}
          {bio.draft ? ` · Drafted ${bio.draft.year}, round ${bio.draft.round} (#${bio.draft.overall} overall) by ${bio.draft.team}` : ' · Undrafted'}
        </p>
      )}
    </div>
  )
}
