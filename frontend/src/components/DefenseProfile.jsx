import { useEffect, useState } from 'react'
import { CompareChart } from './Charts.jsx'
import { seasonLabel } from '../career.js'
import { fmtToi } from '../format.js'

const STATS = [
  { id: 'hits', label: 'Hits' },
  { id: 'blocks', label: 'Blocks' },
  { id: 'takeaways', label: 'Takeaways' },
  { id: 'giveaways', label: 'Giveaways', note: 'fewer is better' },
]
const NET = { id: 'net_takeaways', label: 'Net take-aways' }

const idx = (v) => (v == null ? '–' : `${v.toFixed(2)}×`)
const signed = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`)
const lastName = (full) => full.split(' ').slice(1).join(' ') || full

function useDefense(id) {
  const [result, setResult] = useState({ id: null, data: null })
  useEffect(() => {
    let ignore = false
    fetch(`/api/players/${id}/defense`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setResult({ id, data }))
      .catch(() => !ignore && setResult({ id, data: null }))
    return () => { ignore = true }
  }, [id])
  return result.id === id ? result.data : null
}

const EXPLAIN =
  'Rates are per 60 minutes. The multiplier compares them with the league average at the same role that season ' +
  '(1.00× is average, 1.50× is 50% higher), which keeps seasons comparable even though the NHL has counted these ' +
  'events differently over time. Hits and blocks describe style, not quality.'

/** One player's hits, blocks, takeaways and giveaways against the league, season by season (2005-06 on). */
export default function DefenseProfile({ playerId }) {
  const data = useDefense(playerId)
  if (!data || data.seasons.length === 0) return null
  const { career, seasons } = data

  return (
    <section>
      <h2>Defensive profile vs. the league</h2>
      <p className="sub">{EXPLAIN} Seasons under {data.min_gp} games are greyed out. Tracked since {seasonLabel(data.first_tracked)}.</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left">Season</th><th className="left">Team</th><th>GP</th><th>TOI</th>
              {STATS.map((s) => <th key={s.id} title={s.note}>{s.label}/60</th>)}
              <th title="Takeaways minus giveaways per 60, against the league's rate">Net T–G/60</th>
            </tr>
          </thead>
          <tbody>
            {seasons.map((s) => (
              <tr key={s.season_id} className={s.qualified ? '' : 'muted'}>
                <td className="left">{seasonLabel(s.season_id)}</td>
                <td className="left">{s.team}</td>
                <td>{s.games_played}</td>
                <td>{fmtToi(s.toi_per_game_sec)}</td>
                {STATS.map((st) => {
                  const c = s.stats[st.id]
                  return (
                    <td key={st.id} title={`${c.percentile}th percentile among same-role skaters`}>
                      {c.rate.toFixed(2)} <small>{idx(c.index)}</small>
                    </td>
                  )
                })}
                <td title={`${s.stats.net_takeaways.percentile}th percentile`}>{signed(s.stats.net_takeaways.diff)}</td>
              </tr>
            ))}
            {career && (
              <tr className="total">
                <td className="left" colSpan={4}><strong>Since {seasonLabel(seasons[0].season_id).slice(0, 4)}</strong></td>
                {STATS.map((st) => (
                  <td key={st.id}><strong>{career[st.id].rate.toFixed(2)}</strong> <small>{idx(career[st.id].index)}</small></td>
                ))}
                <td><strong>{signed(career.net_takeaways.diff)}</strong></td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="axis-note">Net T–G is shown as a difference from the league rate, because the league's net is negative.</p>
    </section>
  )
}

/** Defensive style for the players on the Compare page: since-2005-06 totals and a by-age chart. */
export function DefenseCompare({ players }) {
  const [stat, setStat] = useState('hits')
  const [byId, setById] = useState({})

  useEffect(() => {
    players.filter((p) => !(p.id in byId)).forEach((p) => {
      setById((m) => ({ ...m, [p.id]: null }))
      fetch(`/api/players/${p.id}/defense`)
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => setById((m) => ({ ...m, [p.id]: d })))
        .catch(() => {})
    })
  }, [players, byId])

  const loaded = players.map((p) => ({ ...p, def: byId[p.id] })).filter((p) => p.def?.seasons.length)
  if (loaded.length === 0) return null
  const missing = players.length - loaded.length

  const series = loaded
    .map((p) => ({
      id: p.id, slot: p.slot, name: lastName(p.name),
      points: p.def.seasons.filter((s) => s.qualified && s.age != null && s.stats[stat].index != null)
        .map((s) => ({ x: s.age, y: s.stats[stat].index })),
    }))
    .filter((s) => s.points.length)
  const top = Math.max(2, Math.ceil(Math.max(1, ...series.flatMap((s) => s.points.map((p) => p.y))) * 2) / 2)
  const yDomain = { min: 0, max: top, ticks: Array.from({ length: top * 2 + 1 }, (_, i) => i / 2) }
  const label = STATS.find((s) => s.id === stat).label.toLowerCase()

  return (
    <>
      <h2>Defensive style vs. the league</h2>
      <p className="sub">
        Since {seasonLabel(20052006)}, the first season the NHL counted these. {EXPLAIN}
        {missing > 0 && ` ${missing} selected player${missing > 1 ? 's have' : ' has'} no games since then.`}
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left" />
              {loaded.map((p) => <th key={p.id}><i className={`key box cmp-box-${p.slot}`} /> {p.name}</th>)}
            </tr>
          </thead>
          <tbody>
            {STATS.map((st) => (
              <tr key={st.id}>
                <td className="left">{st.label}/60{st.note ? ` (${st.note})` : ''}</td>
                {loaded.map((p) => {
                  const c = p.def.career?.[st.id]
                  return <td key={p.id}>{c ? <>{c.rate.toFixed(2)} <small>{idx(c.index)}</small></> : '–'}</td>
                })}
              </tr>
            ))}
            <tr>
              <td className="left">{NET.label}/60 (vs. league)</td>
              {loaded.map((p) => <td key={p.id}>{signed(p.def.career?.net_takeaways.diff)}</td>)}
            </tr>
            <tr>
              <td className="left">Seasons / games</td>
              {loaded.map((p) => <td key={p.id}>{p.def.seasons.length} / {p.def.seasons.reduce((t, s) => t + s.games_played, 0)}</td>)}
            </tr>
          </tbody>
        </table>
      </div>
      {series.length > 0 && (
        <>
          <div className="tabs" role="tablist">
            {STATS.map((s) => (
              <button key={s.id} role="tab" aria-selected={stat === s.id} className={stat === s.id ? 'on' : ''} onClick={() => setStat(s.id)}>{s.label}</button>
            ))}
          </div>
          <CompareChart
            title={`${STATS.find((s) => s.id === stat).label} per 60 vs. league average, by age`}
            series={series}
            xLabel="Age"
            yLabel={`${label} per 60 as a multiple of the league average (1.0 = average), seasons with ${loaded[0].def.min_gp}+ games`}
            yDomain={yDomain}
            yFmt={(v) => `${v.toFixed(1)}×`}
          />
        </>
      )}
    </>
  )
}
