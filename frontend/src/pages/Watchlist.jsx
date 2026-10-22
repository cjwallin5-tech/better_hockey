import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import DigestToggle from '../components/DigestToggle.jsx'
import { useWatchlist } from '../watchlist.js'

/** Players and teams followed in the daily email. Add from here, or with the Watch button on a player or team page. */
export default function Watchlist() {
  const { signedIn, status, items, limit, error, toggle } = useWatchlist()
  const [pool, setPool] = useState(null) // everything that can be watched
  const [query, setQuery] = useState('')

  useEffect(() => {
    if (!signedIn) return
    Promise.all([
      fetch('/api/skaters').then((r) => r.json()), fetch('/api/goalies').then((r) => r.json()), fetch('/api/teams').then((r) => r.json()),
    ]).then(([skaters, goalies, teams]) => setPool([
      ...skaters.map((r) => ({ kind: 'player', ref: String(r.player_id), name: r.name, detail: `${r.team} · ${r.position}`, path: `/player/${r.player_id}` })),
      ...goalies.goalies.map((r) => ({ kind: 'player', ref: String(r.player_id), name: r.name, detail: `${r.team} · G`, path: `/goalie/${r.player_id}` })),
      ...teams.map((t) => ({ kind: 'team', ref: t.abbrev, name: t.name, detail: t.abbrev, path: `/team/${t.abbrev}` })),
    ])).catch(() => setPool([]))
  }, [signedIn])

  const watched = useMemo(() => new Set(items.map((i) => `${i.kind}:${i.ref}`)), [items])
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q || !pool) return []
    return pool.filter((p) => p.name.toLowerCase().includes(q) && !watched.has(`${p.kind}:${p.ref}`)).slice(0, 8)
  }, [query, pool, watched])
  const pathOf = useMemo(() => new Map((pool ?? []).map((p) => [`${p.kind}:${p.ref}`, p.path])), [pool])

  if (!signedIn) {
    return (
      <main>
        <header><h1>Watchlist</h1><p>Follow players and teams outside your fantasy roster and get a section about them in the morning email.</p></header>
        <p className="status"><Link to="/account">Log in</Link> to keep a watchlist.</p>
      </main>
    )
  }

  const group = (kind) => items.filter((i) => i.kind === kind)
  const list = (kind, title) => group(kind).length > 0 && (
    <section>
      <h2>{title}</h2>
      <ul className="plain-list">
        {group(kind).map((i) => (
          <li key={i.ref}>
            {pathOf.get(`${i.kind}:${i.ref}`) ? <Link to={pathOf.get(`${i.kind}:${i.ref}`)}>{i.name}</Link> : i.name}{' '}
            <button className="link-button" onClick={() => toggle(i.kind, i.ref, i.name)}>Remove</button>
          </li>
        ))}
      </ul>
    </section>
  )

  return (
    <main>
      <header>
        <h1>Watchlist</h1>
        <p>
          Follow players and teams outside your fantasy roster. The morning email gets a Watchlist section with their games
          today, who is hot or cold, role changes and career milestones that are close or just reached.
        </p>
      </header>
      <div className="picker">
        <div className="search-box">
          <input type="search" placeholder="Add a player or team…" value={query} onChange={(e) => setQuery(e.target.value)} />
          {matches.length > 0 && (
            <ul className="results">
              {matches.map((m) => (
                <li key={`${m.kind}:${m.ref}`}>
                  <button onClick={() => { toggle(m.kind, m.ref, m.name); setQuery('') }}>{m.name} <span>{m.detail}</span></button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <span className="muted">{items.length} of {limit}</span>
      </div>
      {error && <p className="notice" role="alert">{error}</p>}
      {status === 'loading' && <p className="status">Loading…</p>}
      {status === 'ready' && items.length === 0 && <p className="status">Nothing yet. Search above, or use the Watch button on a player or team page.</p>}
      {list('player', 'Players')}
      {list('team', 'Teams')}
      <DigestToggle />
    </main>
  )
}
