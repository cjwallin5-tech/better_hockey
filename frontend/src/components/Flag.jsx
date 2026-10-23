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

/** A flag for a country code the page already has (the NHL's three-letter codes, like CAN), nothing for an unknown one. */
export function CountryFlag({ code }) {
  const info = code && countryInfo(code)
  if (!info) return null
  return <img className="flag" src={`/flags/${info.code2}.png`} height="22" alt={info.name} title={info.name} />
}
