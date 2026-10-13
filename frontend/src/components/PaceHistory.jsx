import { useEffect, useMemo, useState } from 'react'
import { CompareChart } from './Charts.jsx'
import { seasonLabel } from '../career.js'

const EARLY_GAMES = 20
const STATS = [['points', 'Points'], ['goals', 'Goals'], ['assists', 'Assists']]

/**
 * This season's running total against past seasons, by game number. `base` is the API path without
 * the query string; players can switch between points, goals and assists.
 */
export default function PaceHistory({ base, title, selectable = false, unit = 'points' }) {
  const [stat, setStat] = useState('points')
  const [range, setRange] = useState(null) // null = decide from games played
  const [result, setResult] = useState({ key: null, data: null })
  const key = `${base}?${stat}`

  useEffect(() => {
    let ignore = false
    fetch(selectable ? `${base}?stat=${stat}` : base)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setResult({ key, data }))
      .catch(() => !ignore && setResult({ key, data: null }))
    return () => { ignore = true }
  }, [base, stat, selectable, key])

  const data = result.key === key ? result.data : null
  const current = data?.seasons.find((s) => s.current)
  const showEarly = range ? range === 'early' : (current?.games ?? 0) < EARLY_GAMES

  const { series, summary } = useMemo(() => {
    if (!data || !current) return { series: [], summary: null }
    const cap = showEarly ? EARLY_GAMES : data.games_per_season
    const built = data.seasons
      .filter((s) => s.totals.length > 0)
      .map((s, i) => ({
        id: s.season_id,
        slot: i + 1, // current season is first, so it gets the lead color; older seasons fade to grays
        name: seasonLabel(s.season_id),
        points: s.totals.slice(0, cap).map((y, g) => ({ x: g + 1, y })),
      }))
    const n = current.games
    let text = null
    if (n > 0) {
      const same = data.seasons.filter((s) => !s.current && s.totals.length >= n).map((s) => ({ season: s.season_id, v: s.totals[n - 1] }))
      if (same.length) {
        const avg = same.reduce((t, x) => t + x.v, 0) / same.length
        text = `After ${n} game${n > 1 ? 's' : ''}: ${current.totals[n - 1]} ${unit}. Past seasons at the same point: ${same.map((x) => `${x.v} (${seasonLabel(x.season)})`).join(', ')} — average ${avg.toFixed(1)}.`
      }
    }
    return { series: built, summary: text }
  }, [data, current, showEarly, unit])

  if (!data || series.length === 0 || !current || current.games === 0) return null

  return (
    <section className="pace-history">
      <div className="controls">
        {selectable && (
          <div className="tabs" role="tablist">
            {STATS.map(([id, label]) => (
              <button key={id} role="tab" aria-selected={stat === id} className={stat === id ? 'on' : ''} onClick={() => setStat(id)}>{label}</button>
            ))}
          </div>
        )}
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={showEarly} className={showEarly ? 'on' : ''} onClick={() => setRange('early')}>First {EARLY_GAMES} games</button>
          <button role="tab" aria-selected={!showEarly} className={!showEarly ? 'on' : ''} onClick={() => setRange('full')}>Full season</button>
        </div>
      </div>
      {summary && <p className="sub">{summary}</p>}
      <CompareChart
        title={title}
        series={series}
        xLabel="Game"
        yLabel={`running total of ${selectable ? STATS.find((s) => s[0] === stat)[1].toLowerCase() : unit}`}
      />
    </section>
  )
}
