import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

// The server writes the right <title> into the first page it serves (backend/previews.py), but moving between pages inside the app
// doesn't reload anything, so the tab would keep the first page's name. This asks the API for each new page's title.

/** What to ask the API about for a page: its path, plus the query only where the title depends on it (the players in /compare). */
export const titleUrl = (pathname, search) => pathname + (pathname === '/compare' ? search : '')

const SITE_TITLE = 'Faceoff'

export function usePageTitle() {
  const { pathname, search } = useLocation()
  const url = titleUrl(pathname, search)
  useEffect(() => {
    let current = true // a slow answer for a page we have already left must not overwrite a newer one
    const set = (t) => { if (current) document.title = t || SITE_TITLE }
    fetch(`/api/share/title?url=${encodeURIComponent(url)}`)
      .then((r) => (r.ok ? r.text() : null))
      .then(set)
      .catch(() => set(null))
    return () => { current = false }
  }, [url])
}
