import { useState } from 'react'

// The Hockey Hall of Fame's emblem, from the museum's own site. If it ever stops loading, the small text badge stands in.
const EMBLEM = 'https://www.hhof.com/favicon/apple-touch-icon.png'

/** Marks a Hockey Hall of Fame member with the Hall's emblem (a round picture), so it needs no words. */
export default function HhofMark({ size = 22 }) {
  const [failed, setFailed] = useState(false)
  if (failed) return <span className="badge" title="Hockey Hall of Fame">HHOF</span>
  return (
    <img
      className="hhof-mark" src={EMBLEM} alt="Hockey Hall of Fame" title="Hockey Hall of Fame"
      width={size} height={size} loading="lazy" onError={() => setFailed(true)}
    />
  )
}
