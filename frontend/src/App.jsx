import { useEffect, useMemo, useState } from 'react'

const fmt1 = (v) => (v == null ? '–' : v.toFixed(1))
const fmtToi = (sec) =>
  sec == null ? '–' : `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, '0')}`

export default function App() {
  const [meta, setMeta] = useState(null)
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [position, setPosition] = useState('ALL')
  const [minGp, setMinGp] = useState(1)
  const [sort, setSort] = useState({ key: 'points', dir: 'desc' })

  useEffect(() => {
    Promise.all([
      fetch('/api/meta').then((r) => r.json()),
      fetch('/api/skaters').then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`)
        return r.json()
      }),
    ])
      .then(([m, s]) => {
        setMeta(m)
        setRows(s)
      })
      .catch((e) => setError(e.message))
  }, [])

  const columns = useMemo(() => {
    const games = meta?.games_per_season ?? 84
    const window = meta?.recent_window ?? 10
    return [
      { key: 'name', label: 'Player', text: true },
      { key: 'team', label: 'Team', text: true },
      { key: 'position', label: 'Pos', text: true },
      { key: 'games_played', label: 'GP' },
      { key: 'goals', label: 'G' },
      { key: 'assists', label: 'A' },
      { key: 'points', label: 'P' },
      { key: 'point_pace', label: `Pace (${games})`, fmt: fmt1, accent: true },
      { key: 'recent_points', label: `L${window} P` },
      { key: 'recent_pace', label: `L${window} Pace`, fmt: fmt1, accent: true },
      { key: 'plus_minus', label: '+/-' },
      { key: 'toi_per_game_sec', label: 'TOI', fmt: fmtToi },
      { key: 'hits', label: 'Hits' },
      { key: 'blocked_shots', label: 'BLK' },
      { key: 'takeaways', label: 'TK' },
      { key: 'giveaways', label: 'GV' },
      { key: 'hits_per60', label: 'Hits/60', fmt: fmt1 },
      { key: 'blocks_per60', label: 'BLK/60', fmt: fmt1 },
    ]
  }, [meta])

  const visible = useMemo(() => {
    if (!rows) return []
    const q = search.trim().toLowerCase()
    const filtered = rows.filter(
      (r) =>
        r.games_played >= minGp &&
        (position === 'ALL' ||
          (position === 'F' ? r.position !== 'D' : r.position === position)) &&
        (!q || r.name.toLowerCase().includes(q) || (r.team ?? '').toLowerCase().includes(q)),
    )
    const { key, dir } = sort
    const sign = dir === 'asc' ? 1 : -1
    return filtered.sort((a, b) => {
      const x = a[key]
      const y = b[key]
      if (x == null && y == null) return 0
      if (x == null) return 1 // nulls always last
      if (y == null) return -1
      return (typeof x === 'string' ? x.localeCompare(y) : x - y) * sign
    })
  }, [rows, search, position, minGp, sort])

  const onSort = (col) =>
    setSort((s) =>
      s.key === col.key
        ? { key: col.key, dir: s.dir === 'desc' ? 'asc' : 'desc' }
        : { key: col.key, dir: col.text ? 'asc' : 'desc' },
    )

  if (error) return <main><p className="status">Couldn't load stats: {error}</p></main>
  if (!rows) return <main><p className="status">Loading…</p></main>

  const season = meta ? `${String(meta.season_id).slice(0, 4)}–${String(meta.season_id).slice(6)}` : ''

  return (
    <main>
      <header>
        <h1>Skater Stats <span>{season}</span></h1>
        <p>
          Pace projects points over {meta.games_per_season} games. L{meta.recent_window} Pace
          uses only each player's last {meta.recent_window} games.
        </p>
      </header>

      <div className="controls">
        <input
          type="search"
          placeholder="Search player or team"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={position} onChange={(e) => setPosition(e.target.value)}>
          <option value="ALL">All positions</option>
          <option value="F">Forwards</option>
          <option value="C">Centers</option>
          <option value="L">Left wings</option>
          <option value="R">Right wings</option>
          <option value="D">Defense</option>
        </select>
        <label>
          Min GP
          <input
            type="number"
            min="1"
            value={minGp}
            onChange={(e) => setMinGp(Math.max(1, Number(e.target.value) || 1))}
          />
        </label>
        <span className="count">{visible.length} players</span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={c.text ? 'left' : ''}
                  onClick={() => onSort(c)}
                  aria-sort={
                    sort.key === c.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'
                  }
                >
                  {c.label}
                  {sort.key === c.key && <i>{sort.dir === 'asc' ? ' ▲' : ' ▼'}</i>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <tr key={r.player_id}>
                {columns.map((c) => (
                  <td key={c.key} className={(c.text ? 'left ' : '') + (c.accent ? 'accent' : '')}>
                    {r[c.key] == null ? '–' : c.fmt ? c.fmt(r[c.key]) : r[c.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  )
}
