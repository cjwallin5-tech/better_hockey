import { useEffect, useState } from 'react'

const STALE_HOURS = 30 // the nightly job runs every ~24h, so older than this means a run was missed

/** Footer line saying when the data was last refreshed, with a warning once it looks stale. */
export default function Freshness() {
  const [updated, setUpdated] = useState(null)
  useEffect(() => {
    fetch('/api/meta').then((r) => r.json()).then((m) => m.updated_at && setUpdated({ at: new Date(m.updated_at), stale: Date.now() - new Date(m.updated_at).getTime() > STALE_HOURS * 36e5 })).catch(() => {})
  }, [])
  if (!updated) return null
  const { at, stale } = updated
  return (
    <footer className={`freshness ${stale ? 'stale' : ''}`}>
      Stats last updated {at.toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
      {stale && ' — this looks out of date; the nightly refresh may have failed.'}
    </footer>
  )
}
