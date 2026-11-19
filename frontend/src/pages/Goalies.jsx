import { useEffect, useMemo, useState } from 'react'
import RankBy from '../components/RankBy.jsx'
import Avatar from '../components/Avatar.jsx'
import RankBadge from '../components/RankBadge.jsx'
import { placesFor } from '../rank.js'
import { Link } from 'react-router-dom'
import { useUrlSync } from '../urlState.js'
import { fmt1, STABLE_GP, fmtSv, fmt2 } from '../format.js'
import { describe } from '../glossary.js'
import SeasonSwitch from '../components/SeasonSwitch.jsx'
import { seasonLabel } from '../career.js'
import PageSkeleton from '../components/Skeleton.jsx'
import PageShell from '../components/PageShell.jsx'
import Info from '../components/Info.jsx'
import { getJson } from '../lists.js'

const fmtSigned = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`)
const fmtMinutes = (sec) => (sec == null ? '–' : `${Math.floor(sec / 60)}`)

// The stats people rank goalies by most, per view.
const QUICK_RANK = {
  overview: [['wins', 'Wins'], ['save_pct', 'SV%'], ['gaa', 'GAA'], ['gsaa', 'GSAA'], ['shutouts', 'Shutouts'], ['quality_start_pct', 'QS%'], ['games_played', 'Games']],
  shootouts: [['so_saves', 'SO saves'], ['so_sv_pct', 'SO SV%'], ['so_faced', 'SO faced']],
  splits: [['save_pct', 'SV%'], ['ev_save_pct', 'EV SV%'], ['pp_save_pct', 'PK SV%'], ['sh_save_pct', 'PP SV%']],
}

const VIEWS = [
  { id: 'overview', label: 'Overview', defaultSort: 'gsaa', note: 'GSAA = goals saved above average: the goals a league-average goalie would have allowed on the same shots, minus the goals actually allowed. Positive is better than average.' },
  { id: 'splits', label: 'Strength splits', defaultSort: 'ev_save_pct', note: 'Save percentage at even strength (EV), on the penalty kill (PP shots against) and when the team is on the power play (SH shots against).' },
  { id: 'shootouts', label: 'Shootouts & penalty shots', defaultSort: 'so_faced', note: 'Shootout and penalty shots faced this season, from play-by-play (a miss wide is not counted as faced). Only goalies who faced one are listed.' },
]

// Columns past seasons don't have: those built from this season's appearance-by-appearance data, and the goalie scoring lines.
const CURRENT_ONLY = new Set(['recent_save_pct', 'recent_gaa', 'recent_gsaa', 'really_bad_starts', 'goals', 'assists', 'pim'])

export default function Goalies({ embedded = false }) {
  const initial = new URLSearchParams(window.location.search)
  const [data, setData] = useState(null)
  const [season, setSeason] = useState(() => (initial.get('season') ? Number(initial.get('season')) : null)) // null = current
  const [error, setError] = useState(null)
  const [search, setSearch] = useState(() => initial.get('q') ?? '')
  const [minGpInput, setMinGpInput] = useState(() => (initial.get('min_gp') ? Number(initial.get('min_gp')) : null))
  const [viewId, setViewId] = useState(() => (VIEWS.some((v) => v.id === initial.get('view')) ? initial.get('view') : 'overview'))
  const [sort, setSort] = useState(() => ({
    key: initial.get('sort') ?? VIEWS.find((v) => v.id === (initial.get('view') ?? 'overview'))?.defaultSort ?? 'gsaa',
    dir: initial.get('dir') ?? 'desc',
  }))

  useUrlSync([
    ['view', viewId, 'overview'], ['sort', sort.key, VIEWS.find((v) => v.id === viewId)?.defaultSort], ['dir', sort.dir, 'desc'],
    ['season', season, null], ['q', search, ''], ['min_gp', minGpInput, null],
  ])

  useEffect(() => {
    let ignore = false
    getJson(season ? `/api/goalies?season=${season}` : '/api/goalies')
      .then((d) => !ignore && setData(d))
      .catch((e) => !ignore && setError(e.message))
    return () => { ignore = true }
  }, [season])

  // A past season has no appearance-by-appearance data stored, so the last-N columns are left out.
  const isPast = season != null
  useEffect(() => {
    if (isPast && viewId === 'shootouts') { setViewId('overview'); setSort({ key: 'gsaa', dir: 'desc' }) }   // shootouts are only stored for this season
  }, [isPast, viewId])
  const onSeason = (id) => { setData(null); setSeason(id) }

  const rows = data?.goalies
  const recentWindow = data?.recent_window ?? 5
  const maxGp = useMemo(() => Math.max(0, ...(rows ?? []).map((g) => g.games_played)), [rows])
  const minGp = minGpInput ?? Math.max(1, Math.ceil(maxGp / 2))
  const view = VIEWS.find((v) => v.id === viewId)

  const columns = useMemo(() => {
    const recentLow = (g) => g.recent_games < recentWindow
    const stats = {
      overview: [
        { key: 'games_started', label: 'GS' },
        { key: 'wins', label: 'W' },
        { key: 'losses', label: 'L' },
        { key: 'ot_losses', label: 'OTL' },
        { key: 'save_pct', label: 'SV%', fmt: fmtSv, accent: true },
        { key: 'gaa', label: 'GAA', fmt: fmt2, asc: true },
        { key: 'gsaa', label: 'GSAA', fmt: fmtSigned, accent: true },
        { key: 'gsaa_per60', label: 'GSAA/60', fmt: fmtSigned },
        { key: 'shots_against_per60', label: 'SA/60', fmt: fmt1 },
        { key: 'quality_starts', label: 'QS' },
        { key: 'quality_start_pct', label: 'QS%', fmt: fmtSv },
        { key: 'really_bad_starts', label: 'RBS' },
        { key: 'shutouts', label: 'SO' },
        { key: 'goal_support_avg', label: 'Goal supp.', fmt: fmt2 },
        { key: 'toi_sec', label: 'MIN', fmt: fmtMinutes },
        { key: 'goals', label: 'G' },
        { key: 'assists', label: 'A' },
        { key: 'pim', label: 'PIM' },
        { key: 'recent_save_pct', label: `L${recentWindow} SV%`, fmt: fmtSv, lowIf: recentLow },
        { key: 'recent_gaa', label: `L${recentWindow} GAA`, fmt: fmt2, lowIf: recentLow, asc: true },
        { key: 'recent_gsaa', label: `L${recentWindow} GSAA`, fmt: fmtSigned, lowIf: recentLow },
      ],
      shootouts: [
        { key: 'so_faced', label: 'SO SA' },
        { key: 'so_saves', label: 'SO Sv', accent: true },
        { key: 'so_sv_pct', label: 'SO SV%', fmt: fmtSv },
        { key: 'ps_faced', label: 'PS SA' },
        { key: 'ps_saves', label: 'PS Sv' },
      ],
      splits: [
        { key: 'save_pct', label: 'SV%', fmt: fmtSv },
        { key: 'ev_shots_against', label: 'EV SA' },
        { key: 'ev_save_pct', label: 'EV SV%', fmt: fmtSv, accent: true },
        { key: 'pp_shots_against', label: 'PK SA' },
        { key: 'pp_save_pct', label: 'PK SV%', fmt: fmtSv, accent: true },
        { key: 'sh_shots_against', label: 'PP SA' },
        { key: 'sh_save_pct', label: 'PP SV%', fmt: fmtSv },
      ],
    }
    return [
      { key: 'name', label: 'Goalie', text: true },
      { key: 'team', label: 'Team', text: true },
      { key: 'games_played', label: 'GP' },
      ...stats[viewId].filter((c) => !isPast || !CURRENT_ONLY.has(c.key)),
    ]
  }, [viewId, recentWindow, isPast])

  const visible = useMemo(() => {
    if (!rows) return []
    const q = search.trim().toLowerCase()
    const filtered = rows.filter(
      (g) =>
        g.games_played >= minGp &&
        (viewId !== 'shootouts' || g.so_faced > 0 || g.ps_faced > 0) &&
        (!q || g.name.toLowerCase().includes(q) || (g.team ?? '').toLowerCase().includes(q)),
    )
    const sign = sort.dir === 'asc' ? 1 : -1
    return filtered.sort((a, b) => {
      const x = a[sort.key]
      const y = b[sort.key]
      if (x == null && y == null) return 0
      if (x == null) return 1
      if (y == null) return -1
      return (typeof x === 'string' ? x.localeCompare(y) : x - y) * sign
    })
  }, [rows, search, minGp, sort, viewId])

  const places = useMemo(() => placesFor(visible, sort.key), [visible, sort.key])

  const onSort = (col) =>
    setSort((s) =>
      s.key === col.key
        ? { key: col.key, dir: s.dir === 'desc' ? 'asc' : 'desc' }
        : { key: col.key, dir: col.text || col.asc ? 'asc' : 'desc' },
    )

  const onView = (id) => {
    setViewId(id)
    setSort({ key: VIEWS.find((v) => v.id === id).defaultSort, dir: 'desc' })
  }

  if (error) return <PageShell embedded={embedded}><p className="status">Couldn't load goalies: {error}</p></PageShell>
  if (!rows) return <PageShell embedded={embedded}><PageSkeleton /></PageShell>

  return (
    <PageShell embedded={embedded}>
      <SeasonSwitch kind="goalie" value={season} onChange={onSeason} />
      <header>
        <h1>Goalie Stats <span>{seasonLabel(data.season_id)}</span></h1>
        <p>
          League-average save percentage {isPast ? `in ${seasonLabel(data.season_id)}` : 'this season'}: {fmtSv(rows[0]?.league_sv_pct)}.
          <Info label="Recent form">
            {isPast ? 'Last-appearances form is only kept for the current season.' : `L${recentWindow} columns use each goalie's last ${recentWindow} appearances.`}
          </Info>
        </p>
      </header>
      {maxGp < STABLE_GP && (
        <p className="notice">
          Early season: goalies have played at most {maxGp} games, so save percentage and GSAA
          swing wildly (L{recentWindow} columns are dimmed until a goalie has {recentWindow} appearances).
          Goalies below {minGp} GP are hidden by default.
        </p>
      )}

      <div className="tabs" role="tablist">
        {VIEWS.filter((v) => !(isPast && v.id === 'shootouts')).map((v) => (
          <button key={v.id} role="tab" aria-selected={v.id === viewId}
            className={v.id === viewId ? 'on' : ''} onClick={() => onView(v.id)}>
            {v.label}
          </button>
        ))}
      </div>
      <p className="view-note">{view.note}</p>
      <RankBy
        options={(QUICK_RANK[viewId] ?? []).filter(([key]) => columns.some((c) => c.key === key)).map(([key, label]) => ({ key, label }))}
        sort={sort}
        onPick={(key) => onSort(columns.find((c) => c.key === key))}
      />

      <div className="controls">
        <input type="search" placeholder="Search goalie or team" value={search}
          onChange={(e) => setSearch(e.target.value)} />
        <label>
          Min GP
          <input type="number" min="1" value={minGp}
            onChange={(e) => setMinGpInput(Math.max(1, Number(e.target.value) || 1))} />
        </label>
        <span className="count">{visible.length} goalies</span>
      </div>

      <div className="table-wrap">
        <table className="board">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} className={c.text ? 'left' : ''} title={describe(c.label)} onClick={() => onSort(c)}
                  aria-sort={sort.key === c.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                  {c.label}
                  {sort.key === c.key && <i>{sort.dir === 'asc' ? ' ▲' : ' ▼'}</i>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((g, rankIndex) => (
              <tr key={g.player_id}>
                {columns.map((c) => (
                  <td key={c.key}
                    className={(c.text ? 'left ' : '') + (c.accent ? 'accent ' : '') + (c.lowIf?.(g) ? 'low ' : '') + (sort.key === c.key ? 'sorted' : '')}>
                    {c.key === 'name' ? (
                      <span className="player-cell"><RankBadge n={places[rankIndex].rank} tied={places[rankIndex].tied} /><Avatar playerId={g.player_id} team={g.team} season={season ?? undefined} name={g.name} /><Link to={`/goalie/${g.player_id}`}>{g.name}</Link></span>
                    ) : c.key === 'team' && g.team ? (
                      g.team.split(',').map((abbr, i) => (
                        <span key={abbr}>{i > 0 && ','}<Link to={`/team/${abbr}`}>{abbr}</Link></span>
                      ))
                    ) : g[c.key] == null ? '–' : c.fmt ? c.fmt(g[c.key]) : g[c.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PageShell>
  )
}
