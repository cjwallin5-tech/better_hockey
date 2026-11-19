import { useEffect, useState } from 'react'

// Big lists (every skater, every goalie) are used by many pages. Keep one copy for a minute, so moving between pages
// does not download them again. Failed requests are not kept.
const TTL_MS = 60_000
const cache = new Map()

/** Promise of the JSON at `url`, shared by everyone who asks within the next minute. Rejects with "API returned <status>". */
export function getJson(url) {
  const hit = cache.get(url)
  if (hit && Date.now() - hit.at < TTL_MS) return hit.promise
  const promise = fetch(url).then((r) => {
    if (!r.ok) throw new Error(`API returned ${r.status}`)
    return r.json()
  })
  cache.set(url, { at: Date.now(), promise })
  promise.catch(() => cache.delete(url))
  return promise
}

/** The JSON at `url` for a component: `null` until it has loaded for this exact url, and `null` if it failed. */
export function useJson(url) {
  const [state, setState] = useState({ url: null, data: null })
  useEffect(() => {
    let ignore = false
    getJson(url).then((data) => !ignore && setState({ url, data })).catch(() => !ignore && setState({ url, data: null }))
    return () => { ignore = true }
  }, [url])
  return state.url === url ? state.data : null
}
