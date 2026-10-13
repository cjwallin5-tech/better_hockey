import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { seasonLabel } from '../career.js'
import { downloadText, toCsv } from '../csv.js'
import { useUrlSync } from '../urlState.js'

const PAGE_SIZE = 50

const int = (v) => (v == null ? '–' : v.toLocaleString())
const dec = (v, d = 2) => (v == null ? '–' : v.toFixed(d))
const pct = (v) => (v == null || v === 0 ? '–' : (v * 100).toFixed(1))
const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))

const COLUMNS = {
  skater: [
    { key: 'first_season', label: 'Debut', fmt: seasonLabel, asc: true },
    { key: 'games_played', label: 'GP', fmt: int },
    { key: 'goals', label: 'G', fmt: int },
    { key: 'assists', label: 'A', fmt: int },
    { key: 'points', label: 'P', fmt: int, accent: true },
    { key: 'points_per_game', label: 'P/GP', fmt: dec, rate: true },
    { key: 'plus_minus', label: '+/-', fmt: int },
    { key: 'pim', label: 'PIM', fmt: int },
    { key: 'pp_goals', label: 'PPG', fmt: int },
    { key: 'pp_points', label: 'PPP', fmt: int },
    { key: 'sh_goals', label: 'SHG', fmt: int },
    { key: 'game_winning_goals', label: 'GWG', fmt: int },
    { key: 'ot_goals', label: 'OTG', fmt: int },
    { key: 'shots', label: 'Shots', fmt: int },
    { key: 'shooting_pct', label: 'S%', fmt: pct, rate: true },
    { key: 'fo_win_pct', label: 'FO%', fmt: pct, rate: true },
    { key: 'hits', label: 'Hits', fmt: int, tracked: true },
    { key: 'blocked_shots', label: 'Blocks', fmt: int, tracked: true },
    { key: 'takeaways', label: 'Takeaways', fmt: int, tracked: true },
    { key: 'giveaways', label: 'Giveaways', fmt: int, tracked: true },
    { key: 'missed_shots', label: 'Missed shots', fmt: int, tracked: true },
    { key: 'shot_attempts', label: 'Shot attempts', fmt: int, tracked: true },
    { key: 'empty_net_goals', label: 'ENG', fmt: int },
    { key: 'first_goals', label: 'First goals', fmt: int },
  ],
  goalie: [
    { key: 'first_season', label: 'Debut', fmt: seasonLabel, asc: true },
    { key: 'games_played', label: 'GP', fmt: int },
    { key: 'games_started', label: 'GS', fmt: int },
    { key: 'wins', label: 'W', fmt: int, accent: true },
    { key: 'losses', label: 'L', fmt: int },
    { key: 'ties', label: 'T', fmt: int },
    { key: 'ot_losses', label: 'OTL', fmt: int },
    { key: 'save_pct', label: 'SV%', fmt: sv, rate: true, accent: true },
    { key: 'gaa', label: 'GAA', fmt: dec, rate: true, asc: true },
    { key: 'shutouts', label: 'SO', fmt: int },
    { key: 'saves', label: 'Saves', fmt: int },
    { key: 'shots_against', label: 'SA', fmt: int },
    { key: 'goals_against', label: 'GA', fmt: int },
    { key: 'toi_sec', label: 'Minutes', fmt: (v) => (v == null ? '–' : Math.round(v / 60).toLocaleString()) },
  ],
}
// Rate stats are meaningless over a handful of games, so sorting by them applies a minimum.
const AUTO_MIN_GP = { skater: 300, goalie: 150 }

export default function AllTime() {
  const initial = new URLSearchParams(window.location.search)
  const initialKind = initial.get('kind') === 'goalie' ? 'goalie' : 'skater'
  const [kind, setKind] = useState(initialKind)
  const [gameType, setGameType] = useState(initial.get('gt') === '3' ? 3 : 2)
  const [search, setSearch] = useState(() => initial.get('q') ?? '')
  const [debouncedSearch, setDebouncedSearch] = useState(() => initial.get('q') ?? '')
  const [position, setPosition] = useState(() => initial.get('pos') ?? '')
  const [country, setCountry] = useState(() => initial.get('country') ?? '')
  const [activeOnly, setActiveOnly] = useState(() => initial.get('active') === '1')
  const [hofOnly, setHofOnly] = useState(() => initial.get('hof') === '1')
  const [debutFrom, setDebutFrom] = useState(() => initial.get('from') ?? '')
  const [debutTo, setDebutTo] = useState(() => initial.get('to') ?? '')
  const [minGpInput, setMinGpInput] = useState(() => initial.get('min_gp') ?? '')
  const [sort, setSort] = useState(() => ({
    key: initial.get('sort') ?? (initialKind === 'skater' ? 'points' : 'wins'),
    dir: initial.get('dir') ?? 'desc',
  }))
  const [page, setPage] = useState(() => Math.max(0, Number(initial.get('page') ?? 1) - 1))
  const [countries, setCountries] = useState([])
  const [result, setResult] = useState({ key: '', data: null, error: null })

  useUrlSync([
    ['kind', kind, 'skater'], ['gt', gameType, 2], ['sort', sort.key, kind === 'skater' ? 'points' : 'wins'], ['dir', sort.dir, 'desc'],
    ['q', search, ''], ['pos', position, ''], ['country', country, ''], ['active', activeOnly, false], ['hof', hofOnly, false],
    ['from', debutFrom, ''], ['to', debutTo, ''], ['min_gp', minGpInput, ''], ['page', page + 1, 1],
  ])

  useEffect(() => {
    fetch(`/api/alltime/${kind}/countries`).then((r) => r.json()).then(setCountries).catch(() => setCountries([]))
  }, [kind])
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  const columns = COLUMNS[kind]
  const sortCol = columns.find((c) => c.key === sort.key)
  const autoMin = sortCol?.rate ? AUTO_MIN_GP[kind] : 0
  const minGp = minGpInput === '' ? autoMin : Number(minGpInput)

  const query = useMemo(() => {
    const p = new URLSearchParams({
      game_type: gameType, sort: sort.key, dir: sort.dir, limit: PAGE_SIZE, offset: page * PAGE_SIZE,
    })
    if (debouncedSearch.trim()) p.set('q', debouncedSearch.trim())
    if (kind === 'skater' && position) p.set('position', position)
    if (country) p.set('country', country)
    if (activeOnly) p.set('active', 'true')
    if (hofOnly) p.set('hof', 'true')
    if (minGp > 0) p.set('min_gp', minGp)
    if (debutFrom) p.set('debut_from', debutFrom)
    if (debutTo) p.set('debut_to', debutTo)
    return p.toString()
  }, [kind, gameType, sort, page, debouncedSearch, position, country, activeOnly, hofOnly, minGp, debutFrom, debutTo])

  const exportAll = async () => {
    const p = new URLSearchParams(query)
    p.set('export', 'true'); p.set('limit', '10000'); p.set('offset', '0')
    const r = await fetch(`/api/alltime/${kind}?${p}`)
    if (!r.ok) return
    const { rows } = await r.json()
    const cols = [
      { key: 'name', label: 'Player' }, ...(kind === 'skater' ? [{ key: 'position', label: 'Pos' }] : []),
      { key: 'birth_country', label: 'Country' }, { key: 'first_season', label: 'Debut season' },
      ...columns.filter((c) => c.key !== 'first_season'),
    ]
    downloadText(`all-time-${kind}s-${gameType === 3 ? 'playoffs' : 'regular-season'}.csv`, toCsv(cols, rows))
  }


  useEffect(() => {
    let ignore = false // a newer query supersedes this one
    fetch(`/api/alltime/${kind}?${query}`)
      .then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`)
        return r.json()
      })
      .then((data) => !ignore && setResult({ key: `${kind}?${query}`, data, error: null }))
      .catch((error) => !ignore && setResult({ key: `${kind}?${query}`, data: null, error: error.message }))
    return () => { ignore = true }
  }, [kind, query])

  // Changing any filter returns to the first page.
  const reset = (setter) => (value) => { setter(value); setPage(0) }

  const switchKind = (k) => {
    setKind(k)
    setSort({ key: k === 'skater' ? 'points' : 'wins', dir: 'desc' })
    setPosition('')
    setCountry('')
    setMinGpInput('')
    setPage(0)
  }

  const onSort = (col) => {
    setSort((s) => (s.key === col.key ? { key: col.key, dir: s.dir === 'desc' ? 'asc' : 'desc' } : { key: col.key, dir: col.asc ? 'asc' : 'desc' }))
    setPage(0)
  }

  const { data, error } = result
  const loading = result.key !== `${kind}?${query}`
  const total = data?.total ?? 0
  const lastPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1)
  const from = total ? page * PAGE_SIZE + 1 : 0
  const to = Math.min(total, (page + 1) * PAGE_SIZE)

  const nameCell = (r) => {
    const route = kind === 'goalie' ? 'goalie' : 'player'
    return (
      <>
        <Link to={`/${route}/${r.player_id}`}>{r.name}</Link>
        {r.hall_of_fame === 'Y' && <span className="badge" title="Hockey Hall of Fame">HHOF</span>}
        {r.active_season && <span className="badge">active</span>}
      </>
    )
  }

  return (
    <main>
      <header>
        <h1>All-time leaders</h1>
        <p>
          Career totals for every {kind === 'skater' ? 'skater' : 'goalie'} in NHL history. Some stats
          are blank for early eras (shots start in 1967-68, plus/minus in 1959-60). Click any
          name for their career page.
        </p>
      </header>

      <div className="controls">
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={kind === 'skater'} className={kind === 'skater' ? 'on' : ''} onClick={() => switchKind('skater')}>Skaters</button>
          <button role="tab" aria-selected={kind === 'goalie'} className={kind === 'goalie' ? 'on' : ''} onClick={() => switchKind('goalie')}>Goalies</button>
        </div>
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={gameType === 2} className={gameType === 2 ? 'on' : ''} onClick={() => reset(setGameType)(2)}>Regular season</button>
          <button role="tab" aria-selected={gameType === 3} className={gameType === 3 ? 'on' : ''} onClick={() => reset(setGameType)(3)}>Playoffs</button>
        </div>
      </div>

      <div className="controls">
        <input type="search" placeholder="Search by name" value={search} onChange={(e) => reset(setSearch)(e.target.value)} />
        {kind === 'skater' && (
          <select value={position} onChange={(e) => reset(setPosition)(e.target.value)} aria-label="Position">
            <option value="">All positions</option>
            <option value="F">Forwards</option>
            <option value="C">Centers</option>
            <option value="L">Left wings</option>
            <option value="R">Right wings</option>
            <option value="D">Defense</option>
          </select>
        )}
        <select value={country} onChange={(e) => reset(setCountry)(e.target.value)} aria-label="Country">
          <option value="">All countries</option>
          {countries.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <label>
          Debuted
          <input type="number" placeholder="from" min="1917" value={debutFrom} onChange={(e) => reset(setDebutFrom)(e.target.value)} />
          –
          <input type="number" placeholder="to" min="1917" value={debutTo} onChange={(e) => reset(setDebutTo)(e.target.value)} />
        </label>
        <label>
          Min GP
          <input type="number" min="0" placeholder={String(autoMin)} value={minGpInput} onChange={(e) => reset(setMinGpInput)(e.target.value)} />
        </label>
        <label className="inline-check">
          <input type="checkbox" checked={activeOnly} onChange={(e) => reset(setActiveOnly)(e.target.checked)} /> Active
        </label>
        <label className="inline-check">
          <input type="checkbox" checked={hofOnly} onChange={(e) => reset(setHofOnly)(e.target.checked)} /> Hall of Famers
        </label>
        <button className="link-button" onClick={exportAll} title="Download every player matching the filters (up to 10,000)">Download CSV</button>
        <span className="count">{loading ? 'Loading…' : `${from.toLocaleString()}–${to.toLocaleString()} of ${total.toLocaleString()}`}</span>
      </div>
      {autoMin > 0 && minGpInput === '' && (
        <p className="view-note">Sorting by a rate stat: showing players with at least {autoMin} games. Change Min GP to adjust.</p>
      )}

      {error ? (
        <p className="status">Couldn't load the board: {error}</p>
      ) : (
        <div className="table-wrap" style={loading ? { opacity: 0.6 } : undefined}>
          <table>
            <thead>
              <tr>
                <th className="rankcol">#</th>
                <th className="left" onClick={() => onSort({ key: 'name', asc: true })} aria-sort={sort.key === 'name' ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                  Player{sort.key === 'name' && <i>{sort.dir === 'asc' ? ' ▲' : ' ▼'}</i>}
                </th>
                {kind === 'skater' && <th className="left">Pos</th>}
                {columns.map((c) => (
                  <th key={c.key} onClick={() => onSort(c)} aria-sort={sort.key === c.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                    {c.label}{sort.key === c.key && <i>{sort.dir === 'asc' ? ' ▲' : ' ▼'}</i>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(data?.rows ?? []).map((r, i) => (
                <tr key={r.player_id}>
                  <td className="rankcol">{(data.offset + i + 1).toLocaleString()}</td>
                  <td className="left">{nameCell(r)}</td>
                  {kind === 'skater' && <td className="left">{r.position}</td>}
                  {columns.map((c) => (
                    <td key={c.key} className={c.accent ? 'accent' : ''}>{c.fmt(r[c.key])}</td>
                  ))}
                </tr>
              ))}
              {data && data.rows.length === 0 && (
                <tr><td className="left" colSpan={columns.length + 3}>No players match these filters.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {kind === 'skater' && (
        <p className="sub">
          Hits, blocks, takeaways, giveaways, missed shots and shot attempts have only been recorded since
          2005-06. Players who finished before then show – , and careers that straddle it only count the
          tracked seasons.
        </p>
      )}

      <div className="pager">
        <button disabled={page === 0 || loading} onClick={() => setPage(0)}>« First</button>
        <button disabled={page === 0 || loading} onClick={() => setPage((p) => p - 1)}>‹ Prev</button>
        <span>Page {(page + 1).toLocaleString()} of {(lastPage + 1).toLocaleString()}</span>
        <button disabled={page >= lastPage || loading} onClick={() => setPage((p) => p + 1)}>Next ›</button>
        <button disabled={page >= lastPage || loading} onClick={() => setPage(lastPage)}>Last »</button>
      </div>
    </main>
  )
}
