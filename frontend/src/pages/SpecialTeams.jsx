import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import TeamLogo from '../components/TeamLogo.jsx'
import { mmss } from '../components/Roles.jsx'
import { useUrlSync } from '../urlState.js'

const n1 = (v) => (v == null ? '–' : v.toFixed(1))
const pct = (v) => (v == null ? '–' : `${(v * 100).toFixed(1)}%`)

// [label, key, format, tooltip, lower is better]
const PP = [
  ['PP %', 'pp_pct', pct, 'Power-play goals per opportunity this season'],
  ['PP xG/60', 'pp_xgf60', n1, 'Expected goals per 60 minutes on the power play: the chances made'],
  ['PP G/60', 'pp_gf60', n1, 'Power-play goals per 60 minutes'],
  ['PP time', 'pp_toi_pg', mmss, 'Power-play time per game'],
]
const PK = [
  ['PK %', 'pk_pct', pct, 'Penalty kills per times short-handed this season'],
  ['PK xGA/60', 'pk_xga60', n1, 'Expected goals against per 60 minutes short-handed: the chances allowed (lower is better)'],
  ['PK GA/60', 'pk_ga60', n1, 'Goals against per 60 minutes short-handed (lower is better)'],
  ['SH time', 'pk_toi_pg', mmss, 'Short-handed time per game (less is better)'],
]
const SORTS = [...PP, ...PK].map(([label, key]) => [key, label])
const LOW_IS_GOOD = new Set(['pk_xga60', 'pk_ga60', 'pk_toi_pg'])

/** Every team's power play and penalty kill, ranked. Click a team for its units. */
export default function SpecialTeams() {
  const initial = new URLSearchParams(window.location.search)
  const [last, setLast] = useState(initial.get('last') ?? '0')
  const [sort, setSort] = useState(initial.get('sort') ?? 'pp_xgf60')
  useUrlSync([['last', last, '0'], ['sort', sort, 'pp_xgf60']])
  const [state, setState] = useState({ last: null, data: null, error: null })

  useEffect(() => {
    let ignore = false
    fetch(`/api/special-teams?last=${last}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`API returned ${r.status}`))))
      .then((data) => !ignore && setState({ last, data, error: null }))
      .catch((error) => !ignore && setState({ last, data: null, error: error.message }))
    return () => { ignore = true }
  }, [last])
  const { data, error } = state.last === last ? state : { data: null, error: null }

  const rows = useMemo(() => {
    if (!data) return []
    const low = LOW_IS_GOOD.has(sort)   // for these, the smallest figure is the best
    const value = (t) => t[sort] ?? (low ? Infinity : -Infinity)   // teams without the figure go last
    return [...data.teams].sort((a, b) => (low ? value(a) - value(b) : value(b) - value(a)) || a.team.localeCompare(b.team))
  }, [data, sort])

  return (
    <main>
      <header>
        <h1>Special teams</h1>
        <p>
          Every team's power play and penalty kill, with expected goals per 60 minutes (the quality of the chances made and allowed)
          next to the NHL's PP% and PK%. A team's units are on its page.
        </p>
      </header>
      <div className="h2h-picks">
        <label className="h2h-pick">Window
          <select value={last} onChange={(e) => setLast(e.target.value)}>
            <option value="0">Season so far</option>
            <option value="10">Last 10 games</option>
            <option value="5">Last 5 games</option>
          </select>
        </label>
        <label className="h2h-pick">Rank by
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th><th className="left">Team</th><th>GP</th>
                {[...PP, ...PK].map(([label, key, , tip]) => <th key={key} title={tip} className={key === sort ? 'accent' : ''}>{label}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((t, i) => (
                <tr key={t.team}>
                  <td>{i + 1}</td>
                  <td className="left"><TeamLogo team={t} /> <Link to={`/team/${t.team}`}>{t.team}</Link></td>
                  <td>{t.games}</td>
                  {[...PP, ...PK].map(([, key, fmt]) => <td key={key} className={key === sort ? 'accent' : ''}>{fmt(t[key])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="sub">
        xG per 60 uses the shots in each situation, so it settles faster than goals do. A power play scoring far above its xG, or a
        penalty kill allowing far below its xG, is running hot and tends to come back to its chances. PP% and PK% are for the whole
        season whatever the window. Early in the year a handful of power plays decide these rankings.
      </p>
    </main>
  )
}
