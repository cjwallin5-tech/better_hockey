import { useEffect, useState } from 'react'
import { trophyIds, trophyMatchKey } from '../trophies.js'

/**
 * A trophy's silhouette (public/trophies/<id>.png, drawn as a mask so it takes the text colour in either theme).
 * Give it the trophy's id, or its name to look the id up. Nothing while the id is unknown.
 */
export default function TrophyImage({ id, name, size = 'sm' }) {
  const [found, setFound] = useState(null)
  useEffect(() => {
    if (id != null || !name) return undefined
    let ignore = false
    trophyIds().then((ids) => !ignore && setFound(ids[trophyMatchKey(name)] ?? null))
    return () => { ignore = true }
  }, [id, name])
  const trophy = id ?? found
  if (trophy == null) return null
  return <span className={`trophy-img ${size}`} style={{ '--sil': `url(/trophies/${trophy}.png)` }} aria-hidden="true" />
}
