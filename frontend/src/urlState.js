import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

/**
 * Keeps list-page filters in the URL so a link reopens the same view. State is read from the URL once
 * on mount (use `params.get(...)` in useState initializers) and written back whenever it changes.
 * `entries` is [[key, value, defaultValue], ...]; values equal to their default are left out.
 */
export function useUrlSync(entries) {
  const [params, setParams] = useSearchParams()
  const signature = JSON.stringify(entries)
  useEffect(() => {
    const next = new URLSearchParams()
    for (const [key, value, fallback] of entries) {
      if (value === null || value === undefined || value === '' || value === fallback || value === false) continue
      next.set(key, value === true ? '1' : String(value))
    }
    if (next.toString() !== params.toString()) setParams(next, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature])
  return params
}
