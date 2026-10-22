import { useEffect, useState } from 'react'
import { countryInfo } from '../countries.js'
import { fetchBio } from '../playerBio.js'

/** The flag of the country a player was born in (what the NHL lists as their nationality); nothing until known. */
export default function Flag({ playerId }) {
  const [code, setCode] = useState(null)
  useEffect(() => {
    let ignore = false
    fetchBio(playerId).then((b) => !ignore && setCode(b?.birth_country ?? null))
    return () => { ignore = true }
  }, [playerId])
  const info = code && countryInfo(code)
  if (!info) return null
  return (
    <img className="flag" src={`/flags/${info.code2}.png`} height="22" alt={info.name} title={info.name} />
  )
}
