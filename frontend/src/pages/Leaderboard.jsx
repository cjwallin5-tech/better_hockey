import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { downloadText, toCsv } from '../csv.js'
import { useUrlSync } from '../urlState.js'
import SavedViews from '../components/SavedViews.jsx'
import { describe } from '../glossary.js'
import SeasonSwitch from '../components/SeasonSwitch.jsx'
import { seasonLabel } from '../career.js'

// Pace from fewer games than this is mostly noise, so it's dimmed and flagged.
const STABLE_GP = 20

const VIEWS = [
  { id: 'scoring', label: 'Scoring', defaultSort: 'points', note: null },
  { id: 'defense', label: 'Defense', defaultSort: 'hits_per60', note: null },
  {
    id: 'possession',
    label: 'Possession',
    defaultSort: 'sat_pct',
    note: 'Shot-attempt stats are 5-on-5. CF/CA = Corsi (all attempts) for/against while on the ice; FF/FA = Fenwick (excludes blocked). Rel = team shot share with the player on minus off the ice. ixG is our own expected-goals model (individual, all strengths); xGF% is the 5v5 share of expected goals while on the ice. L10 columns are computed per game from play-by-play and shift charts over each player\'s last 10 games with shift data; the NHL has published no shift data for some early-season games, so those are skipped (dimmed until a player has 10 usable games).',
  },
  {
    id: 'special',
    label: 'Special teams & usage',
    defaultSort: 'pp_toi_per_game',
    note: 'Ice time per game by situation (EV = even strength, PP = power play, SH = short-handed).',
  },
]

const fmtPct = (v) => (v == null ? '–' : `${(v * 100).toFixed(1)}`)
const fmtSigned1 = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(1)}`)
const fmtSignedPct = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${(v * 100).toFixed(1)}`)
const fmt1 = (v) => (v == null ? '–' : v.toFixed(1))
const fmtToi = (sec) =>
  sec == null ? '–' : `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, '0')}`

// Columns built from this season's game-by-game data, which past seasons don't have.
const CURRENT_ONLY = new Set([
  'point_pace', 'recent_points', 'recent_pace', 'ixg', 'goals_minus_ixg', 'xgf_pct', 'recent_cf_pct', 'recent_ff_pct', 'cf_pct_trend',
])

export default function Leaderboard() {
  const initial = new URLSearchParams(window.location.search) // the URL carries the saved view
  const [meta, setMeta] = useState(null)
  const [season, setSeason] = useState(() => (initial.get('season') ? Number(initial.get('season')) : null)) // null = current
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState(() => initial.get('q') ?? '')
  const [position, setPosition] = useState(() => initial.get('pos') ?? 'ALL')
  const [minGpInput, setMinGpInput] = useState(() => (initial.get('min_gp') ? Number(initial.get('min_gp')) : null)) // null = auto
  const [team, setTeam] = useState(() => initial.get('team') ?? 'ALL')
  const [country, setCountry] = useState(() => initial.get('country') ?? 'ALL')
  const [ageMin, setAgeMin] = useState(() => initial.get('age_min') ?? '')
  const [ageMax, setAgeMax] = useState(() => initial.get('age_max') ?? '')
  const [rookiesOnly, setRookiesOnly] = useState(() => initial.get('rookies') === '1')
  const [viewId, setViewId] = useState(() => (VIEWS.some((v) => v.id === initial.get('view')) ? initial.get('view') : 'scoring'))
  const [sort, setSort] = useState(() => ({
    key: initial.get('sort') ?? VIEWS.find((v) => v.id === (initial.get('view') ?? 'scoring'))?.defaultSort ?? 'points',
    dir: initial.get('dir') ?? 'desc',
  }))

  useUrlSync([
    ['view', viewId, 'scoring'], ['sort', sort.key, VIEWS.find((v) => v.id === viewId)?.defaultSort], ['dir', sort.dir, 'desc'],
    ['season', season, null], ['q', search, ''], ['pos', position, 'ALL'], ['team', team, 'ALL'], ['country', country, 'ALL'],
    ['age_min', ageMin, ''], ['age_max', ageMax, ''], ['rookies', rookiesOnly, false], ['min_gp', minGpInput, null],
  ])

  useEffect(() => {
    fetch('/api/meta').then((r) => r.json()).then(setMeta).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    let ignore = false
    fetch(season ? `/api/skaters?season=${season}` : '/api/skaters')
      .then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`)
        return r.json()
      })
      .then((s) => !ignore && setRows(s))
      .catch((e) => !ignore && setError(e.message))
    return () => { ignore = true }
  }, [season])

  // A past season has no game-by-game data stored, so the pace, last-N-games and expected-goals columns are left out.
  const isPast = season != null
  const onSeason = (id) => { setRows(null); setSeason(id) }

  const maxGp = useMemo(() => Math.max(0, ...(rows ?? []).map((r) => r.games_played)), [rows])
  // Auto cutoff: half the games the busiest player has played, so it scales through the season.
  const minGp = minGpInput ?? Math.max(1, Math.ceil(maxGp / 2))

  const view = VIEWS.find((v) => v.id === viewId)

  const teamOptions = useMemo(
    () => [...new Set((rows ?? []).flatMap((r) => (r.team ?? '').split(',')).filter(Boolean))].sort(),
    [rows],
  )
  const countryOptions = useMemo(
    () => [...new Set((rows ?? []).map((r) => r.birth_country).filter(Boolean))].sort(),
    [rows],
  )
  const filtersActive =
    team !== 'ALL' || country !== 'ALL' || ageMin !== '' || ageMax !== '' || rookiesOnly || position !== 'ALL'
  const clearFilters = () => {
    setTeam('ALL'); setCountry('ALL'); setAgeMin(''); setAgeMax(''); setRookiesOnly(false); setPosition('ALL')
  }

  const columns = useMemo(() => {
    const games = meta?.games_per_season ?? 84
    const window = meta?.recent_window ?? 10
    const recent = (key, label) => ({
      key,
      label: `L${window} ${label}`,
      fmt: fmt1,
      lowIf: (r) => r.recent_games < window,
    })
    // Rolling Corsi uses the last N games that have NHL shift data, so it may span fewer games.
    const onIceLow = (r) => (r.recent_onice_games ?? 0) < window
    const stats = {
      scoring: [
        { key: 'goals', label: 'G' },
        { key: 'assists', label: 'A' },
        { key: 'points', label: 'P' },
        { key: 'point_pace', label: `Pace (${games})`, fmt: fmt1, accent: true, lowIf: (r) => r.games_played < STABLE_GP },
        { key: 'recent_points', label: `L${window} P` },
        { key: 'recent_pace', label: `L${window} Pace`, fmt: fmt1, accent: true, lowIf: (r) => r.recent_games < Math.min(window, STABLE_GP) },
        { key: 'plus_minus', label: '+/-' },
        { key: 'toi_per_game_sec', label: 'TOI', fmt: fmtToi },
        { key: 'shots', label: 'Shots' },
        { key: 'shooting_pct', label: 'S%', fmt: fmtPct },
        { key: 'game_winning_goals', label: 'GWG' },
      ],
      defense: [
        { key: 'hits', label: 'Hits' },
        { key: 'blocked_shots', label: 'BLK' },
        { key: 'takeaways', label: 'TK' },
        { key: 'giveaways', label: 'GV' },
        { key: 'hits_per60', label: 'Hits/60', fmt: fmt1 },
        { key: 'blocks_per60', label: 'BLK/60', fmt: fmt1 },
        { key: 'takeaways_per60', label: 'TK/60', fmt: fmt1 },
        { key: 'giveaways_per60', label: 'GV/60', fmt: fmt1 },
        recent('recent_hits_per60', 'Hits/60'),
        recent('recent_blocks_per60', 'BLK/60'),
        recent('recent_takeaways_per60', 'TK/60'),
        recent('recent_giveaways_per60', 'GV/60'),
      ],
      possession: [
        { key: 'toi_5v5_per_game', label: '5v5 TOI', fmt: fmtToi },
        { key: 'sat_for', label: 'CF' },
        { key: 'sat_against', label: 'CA' },
        { key: 'sat_pct', label: 'CF%', fmt: fmtPct, accent: true },
        { key: 'sat_rel', label: 'CF% Rel', fmt: fmtSignedPct },
        { key: 'usat_for', label: 'FF' },
        { key: 'usat_against', label: 'FA' },
        { key: 'usat_pct', label: 'FF%', fmt: fmtPct, accent: true },
        { key: 'usat_rel', label: 'FF% Rel', fmt: fmtSignedPct },
        { key: 'zone_start_pct_5v5', label: 'OZ Start%', fmt: fmtPct },
        { key: 'ev_goals_for', label: 'EV GF' },
        { key: 'ev_goals_against', label: 'EV GA' },
        { key: 'ev_goals_for_pct', label: 'EV GF%', fmt: fmtPct },
        { key: 'pdo_5v5', label: 'PDO', fmt: fmtPct },
        { key: 'ixg', label: 'ixG', fmt: fmt1 },
        { key: 'goals_minus_ixg', label: 'G − ixG', fmt: fmtSigned1 },
        { key: 'xgf_pct', label: 'xGF%', fmt: fmtPct, accent: true },
        { key: 'recent_cf_pct', label: `L${window} CF%`, fmt: fmtPct, accent: true, lowIf: onIceLow },
        { key: 'recent_ff_pct', label: `L${window} FF%`, fmt: fmtPct, lowIf: onIceLow },
        { key: 'cf_pct_trend', label: `L${window} CF% vs season`, fmt: fmtSignedPct, lowIf: onIceLow },
      ],
      special: [
        { key: 'toi_per_game_sec', label: 'TOI', fmt: fmtToi },
        { key: 'ev_toi_per_game', label: 'EV TOI', fmt: fmtToi },
        { key: 'pp_toi_per_game', label: 'PP TOI', fmt: fmtToi },
        { key: 'sh_toi_per_game', label: 'SH TOI', fmt: fmtToi },
        { key: 'pp_toi_pct', label: 'PP TOI%', fmt: fmtPct },
        { key: 'sh_toi_pct', label: 'SH TOI%', fmt: fmtPct },
        { key: 'shifts_per_game', label: 'Shifts/GP', fmt: fmt1 },
        { key: 'toi_per_shift', label: 'Sec/Shift', fmt: (v) => v.toFixed(0) },
        { key: 'pp_goals', label: 'PPG' },
        { key: 'pp_points', label: 'PPP' },
        { key: 'pp_points_per60', label: 'PPP/60', fmt: fmt1 },
        { key: 'sh_points', label: 'SHP' },
        { key: 'pk_goals_against_per60', label: 'PP GA/60 on ice', fmt: fmt1 },
        { key: 'fo_win_pct', label: 'FO%', fmt: fmtPct },
      ],
    }
    return [
      { key: 'name', label: 'Player', text: true },
      { key: 'team', label: 'Team', text: true },
      { key: 'position', label: 'Pos', text: true },
      { key: 'age', label: 'Age' },
      { key: 'games_played', label: 'GP' },
      ...stats[viewId].filter((c) => !isPast || !CURRENT_ONLY.has(c.key)),
    ]
  }, [meta, viewId, isPast])

  const onView = (id) => {
    setViewId(id)
    setSort({ key: VIEWS.find((v) => v.id === id).defaultSort, dir: 'desc' })
  }

  const visible = useMemo(() => {
    if (!rows) return []
    const q = search.trim().toLowerCase()
    const filtered = rows.filter(
      (r) =>
        r.games_played >= minGp &&
        (position === 'ALL' ||
          (position === 'F' ? r.position !== 'D' : r.position === position)) &&
        (team === 'ALL' || (r.team ?? '').split(',').includes(team)) &&
        (country === 'ALL' || r.birth_country === country) &&
        (ageMin === '' || (r.age != null && r.age >= Number(ageMin))) &&
        (ageMax === '' || (r.age != null && r.age <= Number(ageMax))) &&
        (!rookiesOnly || r.rookie) &&
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
  }, [rows, search, position, minGp, sort, team, country, ageMin, ageMax, rookiesOnly])

  const onSort = (col) =>
    setSort((s) =>
      s.key === col.key
        ? { key: col.key, dir: s.dir === 'desc' ? 'asc' : 'desc' }
        : { key: col.key, dir: col.text ? 'asc' : 'desc' },
    )

  if (error) return <main><p className="status">Couldn't load stats: {error}</p></main>
  if (!rows) return <main><p className="status">Loading…</p></main>

  const seasonName = seasonLabel(season ?? meta?.season_id ?? '')

  return (
    <main>
      <header>
        <h1>Skater Stats <span>{meta || season ? seasonName : ''}</span></h1>
        <p>
          {isPast
            ? `Final regular-season totals for ${seasonName}. Pace, last-games form and expected goals are only kept for the current season.`
            : `Pace projects points over ${meta?.games_per_season ?? 84} games. L${meta?.recent_window ?? 10} Pace uses only each player's last ${meta?.recent_window ?? 10} games.`}
        </p>
      </header>
      <SeasonSwitch kind="skater" value={season} onChange={onSeason} />
      <SavedViews path="/skaters" />

      {maxGp < STABLE_GP && (
        <p className="notice">
          Early season: teams have played at most {maxGp} games, so pace projections are very
          noisy (shown dimmed). Players below {minGp} GP are hidden by default; lower Min GP to
          see everyone.
        </p>
      )}

      <div className="tabs" role="tablist">
        {VIEWS.map((v) => (
          <button
            key={v.id}
            role="tab"
            aria-selected={v.id === viewId}
            className={v.id === viewId ? 'on' : ''}
            onClick={() => onView(v.id)}
          >
            {v.label}
          </button>
        ))}
      </div>
      {view.note && <p className="view-note">{view.note}</p>}

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
        <select value={team} onChange={(e) => setTeam(e.target.value)} aria-label="Team">
          <option value="ALL">All teams</option>
          {teamOptions.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={country} onChange={(e) => setCountry(e.target.value)} aria-label="Country">
          <option value="ALL">All countries</option>
          {countryOptions.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <label>
          Age
          <input type="number" min="16" max="50" placeholder="min" value={ageMin}
            onChange={(e) => setAgeMin(e.target.value)} />
          –
          <input type="number" min="16" max="50" placeholder="max" value={ageMax}
            onChange={(e) => setAgeMax(e.target.value)} />
        </label>
        <label className="inline-check">
          <input type="checkbox" checked={rookiesOnly} onChange={(e) => setRookiesOnly(e.target.checked)} />
          Rookies
        </label>
        <label>
          Min GP
          <input
            type="number"
            min="1"
            value={minGp}
            onChange={(e) => setMinGpInput(Math.max(1, Number(e.target.value) || 1))}
          />
        </label>
        {filtersActive && <button className="link-button" onClick={clearFilters}>Clear filters</button>}
        <button
          className="link-button"
          onClick={() => downloadText('skaters.csv', toCsv(columns, visible))}
          title="Download the rows shown, with raw (unformatted) values"
        >
          Download CSV
        </button>
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
                  title={describe(c.label)}
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
                  <td
                    key={c.key}
                    className={(c.text ? 'left ' : '') + (c.accent ? 'accent ' : '') + (c.lowIf?.(r) ? 'low' : '')}
                    title={c.lowIf?.(r) ? 'Small sample: treat this pace with caution' : undefined}
                  >
                    {c.key === 'name' ? (
                      <>
                        <Link to={`/player/${r.player_id}`}>{r.name}</Link>
                        {r.traded && <span className="badge" title="Played for more than one team this season">↔ traded</span>}
                        {r.games_out >= 2 && (
                          <span className="badge warn" title={`Not in the lineup for the team's last ${r.games_out} games (the NHL feed doesn't say why)`}>
                            out {r.games_out}
                          </span>
                        )}
                      </>
                    ) : c.key === 'team' && r.team ? (
                      r.team.split(',').map((abbr, i) => (
                        <span key={abbr}>
                          {i > 0 && ','}
                          <Link to={`/team/${abbr}`}>{abbr}</Link>
                        </span>
                      ))
                    ) : r[c.key] == null ? (
                      '–'
                    ) : c.fmt ? (
                      c.fmt(r[c.key])
                    ) : (
                      r[c.key]
                    )}
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
