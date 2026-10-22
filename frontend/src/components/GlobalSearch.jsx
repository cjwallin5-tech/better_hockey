import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const MAX_RESULTS = 8

/** Player search for the top bar: current and former skaters and goalies, opening the player's page. Press / to focus it. */
export default function GlobalSearch() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [found, setFound] = useState({ q: '', rows: [] })
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 })
  const box = useRef(null)
  const input = useRef(null)
  const q = query.trim()

  useEffect(() => {
    if (q.length < 2) return undefined
    const ctl = new AbortController()
    const t = setTimeout(() => {
      const get = (kind) => fetch(`/api/alltime/${kind}?q=${encodeURIComponent(q)}&limit=${MAX_RESULTS}`, { signal: ctl.signal })
        .then((r) => (r.ok ? r.json() : { rows: [] }))
        .then((d) => d.rows.map((r) => ({ ...r, kind })))
      Promise.all([get('skater'), get('goalie')])
        .then(([skaters, goalies]) => {
          // Players still active first, then the ones with the longest careers.
          const rows = [...skaters, ...goalies]
            .sort((a, b) => (b.active_season ? 1 : 0) - (a.active_season ? 1 : 0) || b.games_played - a.games_played)
            .slice(0, MAX_RESULTS)
          setFound({ q, rows })
          setActive(0)
        })
        .catch(() => {})
    }, 200)
    return () => { clearTimeout(t); ctl.abort() }
  }, [q])

  useEffect(() => {
    const away = (e) => !box.current?.contains(e.target) && setOpen(false)
    const slash = (e) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName) || document.activeElement?.isContentEditable
      if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey) { e.preventDefault(); input.current?.focus() }
    }
    document.addEventListener('mousedown', away)
    document.addEventListener('keydown', slash)
    return () => { document.removeEventListener('mousedown', away); document.removeEventListener('keydown', slash) }
  }, [])

  const rows = q.length >= 2 && found.q === q ? found.rows : []
  const go = (r) => { setOpen(false); setQuery(''); navigate(`/${r.kind === 'goalie' ? 'goalie' : 'player'}/${r.player_id}`) }
  const show = () => {
    const r = input.current.getBoundingClientRect()
    // Fixed positioning so the list isn't clipped by the scrollable nav bar.
    setPos({ top: r.bottom + 4, left: Math.max(8, Math.min(r.left, window.innerWidth - 328)), width: 320 })
    setOpen(true)
  }
  const onKey = (e) => {
    if (e.key === 'Escape') { setOpen(false); input.current.blur() }
    else if (e.key === 'ArrowDown' && rows.length) { e.preventDefault(); setActive((a) => (a + 1) % rows.length) }
    else if (e.key === 'ArrowUp' && rows.length) { e.preventDefault(); setActive((a) => (a - 1 + rows.length) % rows.length) }
    else if (e.key === 'Enter' && rows[active]) { e.preventDefault(); go(rows[active]) }
  }

  return (
    <div className="global-search" ref={box} role="search">
      <input ref={input} type="search" value={query} placeholder="Search players  /" aria-label="Search players"
        autoComplete="off" onFocus={show} onChange={(e) => { setQuery(e.target.value); show() }} onKeyDown={onKey}
        role="combobox" aria-expanded={open && q.length >= 2} aria-controls="global-search-list" />
      {open && q.length >= 2 && (
        <ul className="search-list" id="global-search-list" role="listbox" style={pos}>
          {rows.length === 0 && <li className="search-empty">{found.q === q ? 'No players found' : 'Searching…'}</li>}
          {rows.map((r, i) => (
            <li key={`${r.kind}-${r.player_id}`} role="option" aria-selected={i === active}>
              <button type="button" className={i === active ? 'on' : ''} onMouseEnter={() => setActive(i)} onClick={() => go(r)}>
                <span>{r.name}</span>
                <small>{r.kind === 'goalie' ? 'G' : r.position}{r.active_season ? ' · active' : r.first_season ? ` · ${String(r.first_season).slice(0, 4)}` : ''}</small>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
