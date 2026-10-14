import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../auth.js'

// The same filters in a different order or with a page number are still the same view.
const normalize = (query) =>
  new URLSearchParams([...new URLSearchParams(query)].filter(([k, v]) => k !== 'page' && v !== '').sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))).toString()

const request = async (url, method, body) => {
  const r = await fetch(url, { method, headers: { 'content-type': 'application/json' }, body: body && JSON.stringify(body) })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(data.detail ?? `Request failed (${r.status})`)
  return data
}

/** Save and reopen the current filters and sort of a leaderboard page, per account. */
export default function SavedViews({ path }) {
  const { user } = useAuth()
  const { search } = useLocation()
  const [views, setViews] = useState([])
  const [naming, setNaming] = useState(false)
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let ignore = false
    if (!user) return undefined
    request(`/api/views?path=${encodeURIComponent(path)}`, 'GET')
      .then((d) => !ignore && setViews(d.views))
      .catch(() => {})
    return () => { ignore = true }
  }, [user, path])

  if (!user) {
    return <p className="saved-views muted"><Link to="/account">Log in</Link> to save filter and sort combinations as views.</p>
  }

  const current = normalize(search)
  // These pages read their filters from the URL once when they load, so opening a view reloads the page.
  const open = (v) => window.location.assign(v.query ? `${path}?${v.query}` : path)

  const save = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const saved = await request('/api/views', 'POST', { name, path, query: search })
      setViews((vs) => [...vs.filter((v) => v.id !== saved.id), saved])
      setNaming(false)
      setName('')
    } catch (err) {
      setError(err.message)
    }
  }

  const remove = async (v) => {
    setError('')
    try {
      await request(`/api/views/${v.id}`, 'DELETE')
      setViews((vs) => vs.filter((x) => x.id !== v.id))
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="saved-views" role="group" aria-label="Saved views">
      <span className="muted">Saved views:</span>
      {views.length === 0 && !naming && <span className="muted">none yet</span>}
      {views.map((v) => (
        <span key={v.id} className={`view-chip${normalize(v.query) === current ? ' on' : ''}`}>
          <button type="button" onClick={() => open(v)} title="Open this view">{v.name}</button>
          <button type="button" className="x" onClick={() => remove(v)} aria-label={`Delete view ${v.name}`}>×</button>
        </span>
      ))}
      {naming ? (
        <form onSubmit={save} className="view-name">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name this view" maxLength={60} required autoFocus />
          <button type="submit">Save</button>
          <button type="button" className="link-button" onClick={() => { setNaming(false); setError('') }}>Cancel</button>
        </form>
      ) : (
        <button type="button" className="link-button" onClick={() => setNaming(true)}>+ Save this view</button>
      )}
      {error && <span className="notice" role="alert">{error}</span>}
    </div>
  )
}
