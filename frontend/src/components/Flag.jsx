import { useEffect, useState } from 'react'
import { countryInfo } from '../countries.js'

// One request per player, shared with anything else that asks while it is in flight or after.
const cache = new Map()
function birthCountry(id) {
  if (!cache.has(id)) {
    cache.set(id, fetch(`/api/players/${id}/career`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.bio?.birth_country ?? null)
      .catch(() => { cache.delete(id); return null }))
  }
  return cache.get(id)
}

/** The flag of the country a player was born in (what the NHL lists as their nationality); nothing until known. */
export default function Flag({ playerId }) {
  const [code, setCode] = useState(null)
  useEffect(() => {
    let ignore = false
    birthCountry(playerId).then((c) => !ignore && setCode(c))
    return () => { ignore = true }
  }, [playerId])
  const info = code && countryInfo(code)
  if (!info) return null
  return (
    <img className="flag" src={`https://flagcdn.com/w40/${info.code2}.png`} srcSet={`https://flagcdn.com/w80/${info.code2}.png 2x`}
      width="30" height="22" alt={info.name} title={info.name} />
  )
}
