import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { CompareChart } from '../components/Charts.jsx'
import { ageInSeason, nhlSeasons, seasonGaa, seasonLabel, seasonSvPct } from '../career.js'
import { fmt1, fmtPct, fmtToi } from '../format.js'
import { DefenseCompare } from '../components/DefenseProfile.jsx'
import { GOALIE_CATS, SKATER_CATS, fantasyPoints, useScoring } from '../fantasy.js'

const MAX_PLAYERS = 3

// Chart metrics per kind. cumulative ones add up across seasons; the others plot each season.
const METRICS = {
  skater: [
    { id: 'p', label: 'Points', cumulative: true, value: (s) => s.p },
    { id: 'g', label: 'Goals', cumulative: true, value: (s) => s.g },
    { id: 'a', label: 'Assists', cumulative: true, value: (s) => s.a },
  ],
  goalie: [
    { id: 'w', label: 'Wins', cumulative: true, value: (s) => s.w },
    { id: 'so', label: 'Shutouts', cumulative: true, value: (s) => s.so },
    { id: 'sv', label: 'Save % by season', cumulative: false, value: seasonSvPct, fmt: (v) => v.toFixed(3).replace(/^0/, ''), rate: { step: 0.01, pad: 0.005, digits: 2 } },
    { id: 'gaa', label: 'GAA by season', cumulative: false, value: seasonGaa, fmt: (v) => v.toFixed(2), rate: { step: 0.5, pad: 0.25, digits: 1 } },
  ],
}

const years = (m) => {
  const a = String(m.first_season ?? '').slice(0, 4)
  return a ? `${m.active_season ? 'active, ' : ''}debut ${a}` : ''
}
const lastName = (full) => full.split(' ').slice(1).join(' ') || full
const num = (v, d = 0) => (v == null ? '–' : Number(v).toFixed(d))
const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))
const signed = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`)

// Axis for a rate metric: padded around the data, ticks on round steps.
function rateDomain(values, { step, pad, digits }) {
  const lo = Math.floor((Math.min(...values) - pad) / step) * step
  const hi = Math.ceil((Math.max(...values) + pad) / step) * step
  const ticks = []
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Number(v.toFixed(digits + 1)))
  return { min: lo, max: hi, ticks }
}

export default function Compare() {
  const [params, setParams] = useSearchParams()
  const { scoring } = useScoring()
  const ids = useMemo(
    () => (params.get('ids') ?? '').split(',').map(Number).filter(Boolean).slice(0, MAX_PLAYERS),
    [params],
  )
  const [skaters, setSkaters] = useState(null)
  const [goalies, setGoalies] = useState(null)
  const [careers, setCareers] = useState({}) // id -> { data } | { error }
  const [query, setQuery] = useState('')
  const [poolKind, setPoolKind] = useState('skater') // which list to search while nothing is selected
  const [metricId, setMetricId] = useState(params.get('metric')) // also lets a link open on a given chart
  const [xMode, setXMode] = useState('season') // 'season' | 'age'
  const [eraFactors, setEraFactors] = useState(null)

  useEffect(() => {
    fetch('/api/skaters').then((r) => r.json()).then(setSkaters).catch(() => setSkaters([]))
    fetch('/api/goalies').then((r) => r.json()).then((d) => setGoalies(d.goalies)).catch(() => setGoalies([]))
    fetch('/api/era-factors').then((r) => (r.ok ? r.json() : null)).then(setEraFactors).catch(() => {})
  }, [])

  useEffect(() => {
    ids.filter((id) => !careers[id]).forEach((id) => {
      fetch(`/api/players/${id}/career`)
        .then(async (r) => {
          if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `API returned ${r.status}`)
          return r.json()
        })
        .then((data) => setCareers((c) => ({ ...c, [id]: { data } })))
        .catch((e) => setCareers((c) => ({ ...c, [id]: { error: e.message } })))
    })
  }, [ids, careers])

  const setIds = (next) => setParams(next.length ? { ids: next.join(',') } : {})
  const skaterById = useMemo(() => new Map((skaters ?? []).map((s) => [s.player_id, s])), [skaters])
  const goalieById = useMemo(() => new Map((goalies ?? []).map((g) => [g.player_id, g])), [goalies])

  // The first player picked decides the kind; goalies and skaters can't be mixed meaningfully.
  const firstBio = careers[ids[0]]?.data?.bio // retired players aren't in the current-season lists
  const kind = ids.length ? (firstBio ? (firstBio.is_goalie ? 'goalie' : 'skater') : goalieById.has(ids[0]) ? 'goalie' : 'skater') : poolKind
  const isGoalie = kind === 'goalie'
  // Era-adjusted scoring: each season's goals and assists scaled to today's scoring level, by role.
  const adjusted = (s, p, stats) => {
    const f = eraFactors?.seasons[String(s.season)]?.[p?.career?.bio?.position === 'D' ? 'D' : 'F']
    if (!f) return null
    return (stats.includes('g') ? s.g * f.goals : 0) + (stats.includes('a') ? s.a * f.assists : 0)
  }
  const eraMetrics = eraFactors && kind === 'skater'
    ? [
        { id: 'ap', label: 'Points (era-adjusted)', era: true, cumulative: true, fmt: (v) => Math.round(v), value: (s, p) => adjusted(s, p, 'ga') },
        { id: 'ag', label: 'Goals (era-adjusted)', era: true, cumulative: true, fmt: (v) => Math.round(v), value: (s, p) => adjusted(s, p, 'g') },
        { id: 'aa', label: 'Assists (era-adjusted)', era: true, cumulative: true, fmt: (v) => Math.round(v), value: (s, p) => adjusted(s, p, 'a') },
      ]
    : []
  const metrics = [...METRICS[kind], ...eraMetrics]
  const metric = metrics.find((m) => m.id === metricId) ?? metrics[0]

  // Search every player in NHL history (the all-time tables), not just this season's rosters.
  const [found, setFound] = useState({ q: '', kind: '', rows: [] })
  useEffect(() => {
    const q = query.trim()
    if (!q) return
    const ctl = new AbortController()
    const t = setTimeout(() => {
      fetch(`/api/alltime/${kind}?q=${encodeURIComponent(q)}&limit=12`, { signal: ctl.signal })
        .then((r) => r.json())
        .then((d) => setFound({ q, kind, rows: d.rows ?? [] }))
        .catch(() => {})
    }, 200)
    return () => { clearTimeout(t); ctl.abort() }
  }, [query, kind])
  const matches = query.trim() && found.q === query.trim() && found.kind === kind
    ? found.rows.filter((r) => !ids.includes(r.player_id)).slice(0, 8)
    : []

  const players = ids.map((id, i) => {
    const season = isGoalie ? goalieById.get(id) : skaterById.get(id)
    const c = careers[id]
    return { id, slot: i + 1, season, career: c?.data, error: c?.error, name: season?.name ?? c?.data?.bio.name ?? `#${id}` }
  })

  const series = players
    .filter((p) => p.career)
    .map((p) => {
      let total = 0
      const points = nhlSeasons(p.career.seasons)
        .map((s, i) => {
          const v = metric.value(s, p)
          if (v == null) return null
          total += metric.cumulative ? v : 0
          const x = xMode === 'age' ? ageInSeason(p.career.bio.birth_date, s.season) : i + 1
          return x == null ? null : { x, y: metric.cumulative ? total : v }
        })
        .filter(Boolean)
      return { id: p.id, slot: p.slot, name: lastName(p.name), points }
    })
    .filter((s) => s.points.length)

  const yDomain = metric.rate && series.length ? rateDomain(series.flatMap((s) => s.points.map((p) => p.y)), metric.rate) : undefined
  const metricLabel = metric.label.toLowerCase()

  const reg = (p) => p.career.career.regularSeason
  const adjustedTotal = (p) => {
    const parts = nhlSeasons(p.career.seasons).map((s) => adjusted(s, p, 'ga')).filter((v) => v != null)
    return parts.length ? parts.reduce((t, v) => t + v, 0) : null
  }
  const poff = (p) => p.career.career.playoffs
  const bestSeason = (p, key) => Math.max(0, ...nhlSeasons(p.career.seasons).map((s) => s[key]))

  // Rows: [label, getter, best ('max'|'min'|null), formatter]
  const careerRows = isGoalie
    ? [
        ['NHL seasons', (p) => nhlSeasons(p.career.seasons).length, 'max'],
        ['Games played', (p) => reg(p)?.gamesPlayed, 'max'],
        ['Games started', (p) => reg(p)?.gamesStarted, 'max'],
        ['Wins', (p) => reg(p)?.wins, 'max'],
        ['Losses', (p) => reg(p)?.losses, null],
        ['OT losses', (p) => reg(p)?.otLosses, null],
        ['Save %', (p) => reg(p)?.savePctg, 'max', sv],
        ['Goals-against average', (p) => reg(p)?.goalsAgainstAvg, 'min', (v) => v.toFixed(2)],
        ['Shutouts', (p) => reg(p)?.shutouts, 'max'],
        ['Shots against', (p) => reg(p)?.shotsAgainst, null],
        ['Best season (wins)', (p) => bestSeason(p, 'w'), 'max'],
        ['Playoff games', (p) => poff(p)?.gamesPlayed ?? 0, null],
        ['Playoff wins', (p) => poff(p)?.wins ?? 0, 'max'],
      ]
    : [
        ['NHL seasons', (p) => nhlSeasons(p.career.seasons).length, 'max'],
        ['Games played', (p) => reg(p)?.gamesPlayed, 'max'],
        ['Goals', (p) => reg(p)?.goals, 'max'],
        ['Assists', (p) => reg(p)?.assists, 'max'],
        ['Points', (p) => reg(p)?.points, 'max'],
        ['Points / game', (p) => (reg(p) ? reg(p).points / reg(p).gamesPlayed : null), 'max', (v) => v.toFixed(2)],
        ...(eraFactors ? [['Points, era-adjusted', (p) => adjustedTotal(p), 'max', (v) => Math.round(v).toLocaleString()]] : []),
        ['Plus/minus', (p) => reg(p)?.plusMinus, 'max'],
        ['Power-play points', (p) => reg(p)?.powerPlayPoints, 'max'],
        ['Game-winning goals', (p) => reg(p)?.gameWinningGoals, 'max'],
        ['Shooting %', (p) => (reg(p)?.shootingPctg ? reg(p).shootingPctg * 100 : null), 'max', (v) => v.toFixed(1)],
        ['Best season (points)', (p) => bestSeason(p, 'p'), 'max'],
        ['Playoff points', (p) => poff(p)?.points ?? 0, 'max'],
        ['Playoff games', (p) => poff(p)?.gamesPlayed ?? 0, null],
        ['Penalty minutes', (p) => reg(p)?.pim, null],
      ]

  // Fantasy value under the league scoring set on the Fantasy team page.
  const fpg = (p) => {
    const r = p.season
    return r?.games_played ? fantasyPoints(r, isGoalie ? GOALIE_CATS : SKATER_CATS, scoring) / r.games_played : null
  }
  const fpTotal = (p) => (p.season ? fantasyPoints(p.season, isGoalie ? GOALIE_CATS : SKATER_CATS, scoring) : null)
  const fantasyRows = [
    ['Fantasy points', fpTotal, 'max', fmt1],
    ['Fantasy points / game', fpg, 'max', (v) => v.toFixed(2)],
  ]

  const seasonRows = isGoalie
    ? [
        ['Games played', (p) => p.season?.games_played, null],
        ['Games started', (p) => p.season?.games_started, null],
        ['Wins', (p) => p.season?.wins, 'max'],
        ['Losses', (p) => p.season?.losses, null],
        ['Save %', (p) => p.season?.save_pct, 'max', sv],
        ['Goals-against average', (p) => p.season?.gaa, 'min', (v) => v.toFixed(2)],
        ['Goals saved above average', (p) => p.season?.gsaa, 'max', signed],
        ['GSAA / 60', (p) => p.season?.gsaa_per60, 'max', signed],
        ['Shots against / 60', (p) => p.season?.shots_against_per60, null, fmt1],
        ['Quality start %', (p) => p.season?.quality_start_pct, 'max', sv],
        ['Even-strength save %', (p) => p.season?.ev_save_pct, 'max', sv],
        ['Penalty-kill save %', (p) => p.season?.pp_save_pct, 'max', sv],
        ['Recent save %', (p) => p.season?.recent_save_pct, 'max', sv],
        ['Shutouts', (p) => p.season?.shutouts, 'max'],
      ]
    : [
        ['Games played', (p) => p.season?.games_played, null],
        ['Goals', (p) => p.season?.goals, 'max'],
        ['Assists', (p) => p.season?.assists, 'max'],
        ['Points', (p) => p.season?.points, 'max'],
        ['Point pace', (p) => p.season?.point_pace, 'max', fmt1],
        ['Plus/minus', (p) => p.season?.plus_minus, 'max'],
        ['Time on ice / game', (p) => p.season?.toi_per_game_sec, null, fmtToi],
        ['Shots', (p) => p.season?.shots, 'max'],
        ['Hits / 60', (p) => p.season?.hits_per60, 'max', fmt1],
        ['Blocks / 60', (p) => p.season?.blocks_per60, 'max', fmt1],
        ['Takeaways / 60', (p) => p.season?.takeaways_per60, 'max', fmt1],
        ['Giveaways / 60', (p) => p.season?.giveaways_per60, 'min', fmt1],
        ['Corsi % (5v5)', (p) => p.season?.sat_pct, 'max', fmtPct],
        ['Even-strength goal share', (p) => p.season?.ev_goals_for_pct, 'max', fmtPct],
        ['Power-play points / 60', (p) => p.season?.pp_points_per60, 'max', fmt1],
      ]

  return (
    <main>
      <header>
        <h1>Compare {isGoalie ? 'goalies' : 'players'}</h1>
        <p>Pick up to {MAX_PLAYERS} {isGoalie ? 'goalies' : 'skaters'}, past or present, to see their careers side by side. Current players also get this season's stats.</p>
      </header>

      {ids.length === 0 && (
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={poolKind === 'skater'} className={poolKind === 'skater' ? 'on' : ''} onClick={() => setPoolKind('skater')}>Skaters</button>
          <button role="tab" aria-selected={poolKind === 'goalie'} className={poolKind === 'goalie' ? 'on' : ''} onClick={() => setPoolKind('goalie')}>Goalies</button>
        </div>
      )}

      <div className="picker">
        <div className="chips">
          {players.map((p) => (
            <span key={p.id} className={`chip cmp-chip-${p.slot}`}>
              <Link to={`/${isGoalie ? 'goalie' : 'player'}/${p.id}`}>{p.name}</Link>
              <button aria-label={`Remove ${p.name}`} onClick={() => setIds(ids.filter((i) => i !== p.id))}>×</button>
            </span>
          ))}
        </div>
        {ids.length < MAX_PLAYERS && (
          <div className="search-box">
            <input
              type="search"
              placeholder={ids.length ? `Add another ${isGoalie ? 'goalie' : 'player'}…` : `Search for a ${isGoalie ? 'goalie' : 'player'}…`}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {matches.length > 0 && (
              <ul className="results">
                {matches.map((m) => (
                  <li key={m.player_id}>
                    <button onClick={() => { setIds([...ids, m.player_id]); setQuery('') }}>
                      {m.name} <span>{isGoalie ? 'G' : m.position}{years(m) && ` · ${years(m)}`}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {ids.length === 0 && <p className="status">Search for a {isGoalie ? 'goalie' : 'player'} above to begin.</p>}
      {players.some((p) => p.error) && (
        <p className="notice">
          Couldn't load career data for {players.filter((p) => p.error).map((p) => p.name).join(', ')}. The NHL
          API may be busy; remove and re-add them to retry.
        </p>
      )}

      {series.length > 0 && (
        <>
          <div className="controls">
            <div className="tabs" role="tablist">
              {metrics.map((m) => (
                <button key={m.id} role="tab" aria-selected={metric.id === m.id} className={metric.id === m.id ? 'on' : ''} onClick={() => setMetricId(m.id)}>
                  {m.label}
                </button>
              ))}
            </div>
            <div className="tabs" role="tablist">
              <button role="tab" aria-selected={xMode === 'season'} className={xMode === 'season' ? 'on' : ''} onClick={() => setXMode('season')}>By NHL season</button>
              <button role="tab" aria-selected={xMode === 'age'} className={xMode === 'age' ? 'on' : ''} onClick={() => setXMode('age')}>By age</button>
            </div>
          </div>
          <CompareChart
            title={metric.cumulative ? `Career ${metricLabel}, cumulative` : metric.label}
            series={series}
            xLabel={xMode === 'age' ? 'Age' : 'NHL season'}
            yLabel={metric.cumulative ? `career ${metricLabel} through that ${xMode === 'age' ? 'age' : 'season'}` : 'each NHL season, all teams combined'}
            yDomain={yDomain}
            yFmt={metric.fmt}
          />
          {metric.era && (
            <p className="sub">
              Era-adjusted: each season's goals and assists are scaled to today's scoring level for the player's role
              (forward or defenseman), so a 1980s season and a 2020s one are on the same footing. Games, ice time and
              power-play share are not adjusted. <Link to="/alltime?v=adjusted">See the all-time era-adjusted leaders →</Link>
            </p>
          )}
        </>
      )}

      {players.some((p) => p.career) && (
        <>
          <h2>Career (NHL regular season)</h2>
          <CompareTable players={players.filter((p) => p.career)} rows={careerRows} />
        </>
      )}

      {!isGoalie && players.some((p) => p.career) && <DefenseCompare players={players.filter((p) => p.career)} />}

      {players.some((p) => p.season) && (
        <>
          <h2>This season ({seasonLabel(players.find((p) => p.season)?.season?.season_id ?? 0)})</h2>
          <CompareTable players={players.filter((p) => p.season)} rows={[...fantasyRows, ...seasonRows]} />
          <p className="sub">Fantasy points use the league scoring on your <Link to="/fantasy">Fantasy team</Link> page.</p>
        </>
      )}
    </main>
  )
}

function CompareTable({ players, rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="left" />
            {players.map((p) => (
              <th key={p.id}><i className={`key box cmp-box-${p.slot}`} /> {p.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, get, best, fmt]) => {
            const vals = players.map((p) => get(p))
            const nums = vals.filter((v) => v != null && !Number.isNaN(v))
            const target = best && nums.length > 1 ? (best === 'max' ? Math.max(...nums) : Math.min(...nums)) : null
            return (
              <tr key={label}>
                <td className="left">{label}</td>
                {vals.map((v, i) => (
                  <td key={players[i].id} className={target != null && v === target ? 'accent' : ''}>
                    {v == null || Number.isNaN(v) ? '–' : fmt ? fmt(v) : num(v)}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
