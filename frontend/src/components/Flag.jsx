import { useEffect, useState } from 'react'
import { countryInfo } from '../countries.js'
import { fetchBio } from '../playerBio.js'

/** The flag of a player's nationality as the NHL lists it (which can differ from where they were born); nothing until known. */
export default function Flag({ playerId }) {
  const [code, setCode] = useState(null)
  useEffect(() => {
    let ignore = false
    fetchBio(playerId).then((b) => !ignore && setCode(b?.nationality ?? null))
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
