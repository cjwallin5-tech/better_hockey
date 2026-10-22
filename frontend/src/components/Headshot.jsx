import { useEffect, useState } from 'react'
import { fetchBio } from '../playerBio.js'

const initials = (name) => (name ?? '').split(/\s+/).filter(Boolean).map((w) => w[0]).slice(0, 2).join('').toUpperCase()

/** A player's picture for the top of their page. The space is held while it loads, and initials stand in when there is no photo. */
export default function Headshot({ playerId, name }) {
  const [url, setUrl] = useState(null)
  const [failedUrl, setFailedUrl] = useState(null)
  useEffect(() => {
    let ignore = false
    fetchBio(playerId).then((b) => !ignore && setUrl(b?.headshot ?? null))
    return () => { ignore = true }
  }, [playerId])
  return url && failedUrl !== url
    ? <img className="headshot headshot-lg" src={url} alt={name ?? ''} width="96" height="96" onError={() => setFailedUrl(url)} />
    : <span className="headshot headshot-lg headshot-blank" aria-hidden="true">{initials(name)}</span>
}
