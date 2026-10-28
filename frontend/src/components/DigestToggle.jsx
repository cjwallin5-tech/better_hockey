import { useEffect, useState } from 'react'

/** Opt in or out of the morning email about the fantasy roster. */
export default function DigestToggle() {
  const [pref, setPref] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let ignore = false
    fetch('/api/digest')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => !ignore && setPref(d))
      .catch(() => {})
    return () => { ignore = true }
  }, [])

  if (!pref) return null

  const change = async (enabled) => {
    setError('')
    try {
      const r = await fetch('/api/digest', {
        method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ enabled }),
      })
      if (!r.ok) throw new Error(`Request failed (${r.status})`)
      setPref(await r.json())
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <section>
      <h2>Daily roster email</h2>
      <label className="check">
        <input type="checkbox" checked={pref.enabled} onChange={(e) => change(e.target.checked)} />
        Email me each morning: which of my players have a game today, who's hot, and who's missing games, plus a section for your watchlist. On Sundays it opens with your best lineup for the coming week, your goalies' starts and which days are heavy or light.
      </label>
      {pref.enabled && !pref.email_configured && (
        <p className="muted">
          This server has no email settings (SMTP_HOST) yet, so nothing will actually be sent until its owner sets them up.
        </p>
      )}
      {error && <p className="notice" role="alert">{error}</p>}
    </section>
  )
}
