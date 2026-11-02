import { useEffect, useState } from 'react'
import { axisValue, ordinal, radarPoint, radarPolygon } from '../scouting.js'
import ShareButtons from './ShareButtons.jsx'

const SIZE = 380
const C = SIZE / 2
const R = 120 // radius of the 100th-percentile ring; labels sit outside it
const RINGS = [25, 50, 75, 100]

function useScouting(id) {
  const [result, setResult] = useState({ id: null, data: null })
  useEffect(() => {
    let ignore = false
    fetch(`/api/skaters/${id}/scouting`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setResult({ id, data }))
      .catch(() => !ignore && setResult({ id, data: null }))
    return () => { ignore = true }
  }, [id])
  return result.id === id ? result.data : null
}

/** series: [{ id, slot (1-3), name, axes }]; every series shares the same axis order. */
function Radar({ series }) {
  const labels = series[0].axes
  const n = labels.length
  const summary = series
    .map((s) => `${s.name}: ${s.axes.map((a) => `${a.label} ${a.percentile == null ? 'no data' : ordinal(a.percentile)}`).join(', ')}`)
    .join('. ')
  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} width="100%" style={{ maxWidth: SIZE }} role="img" aria-label={`Percentile radar. ${summary}`}>
      {RINGS.map((p) => (
        <polygon key={p} points={radarPolygon(Array(n).fill(p), C, C, R)} className="grid" fill="none" />
      ))}
      {labels.map((a, i) => {
        const edge = radarPoint(i, n, 100, C, C, R)
        const text = radarPoint(i, n, 100, C, C, R + 22)
        const anchor = Math.abs(text.x - C) < 8 ? 'middle' : text.x > C ? 'start' : 'end'
        return (
          <g key={a.key}>
            <line x1={C} y1={C} x2={edge.x} y2={edge.y} className="grid" />
            <text x={text.x} y={text.y} textAnchor={anchor} dominantBaseline="middle" className="axis radar-label">{a.label}</text>
          </g>
        )
      })}
      <text x={C + 3} y={C - R * 0.5 - 2} className="axis">50</text>
      {series.map((s) => (
        <g key={s.id}>
          <polygon points={radarPolygon(s.axes.map((a) => a.percentile), C, C, R)} className={`radar-area radar-fill-${s.slot} cmp-line cmp-${s.slot}`} />
          {s.axes.map((a, i) => {
            if (a.percentile == null) return null
            const p = radarPoint(i, n, a.percentile, C, C, R)
            return <circle key={a.key} cx={p.x} cy={p.y} r="3" className={`cmp-dot cmp-fill-${s.slot}`} />
          })}
        </g>
      ))}
    </svg>
  )
}

function AxisTable({ data }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr><th className="left">Measure</th><th>Value</th><th title="Share of same-role skaters this player is at least as good as; higher is better.">Percentile</th></tr>
        </thead>
        <tbody>
          {data.axes.map((a) => (
            <tr key={a.key} title={a.note}>
              <td className="left">{a.label}{a.luck ? ' *' : ''}</td>
              <td>{axisValue(a)} <span className="muted">{a.unit}</span></td>
              <td className="accent">{ordinal(a.percentile)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const list = (xs) => xs.join(', ')

/** Player-page panel: the radar, a one-line read on strengths and weaknesses, and the numbers behind it. */
export default function ScoutingCard({ playerId }) {
  const data = useScouting(playerId)
  if (!data || data.axes.every((a) => a.percentile == null)) return null
  const card = {
    radar: true,
    title: data.name,
    subtitle: `${data.team} · ${data.position} · ${data.games_played} GP · percentile among ${data.peer_count} ${data.peer_group}`,
    labels: data.axes.map((a) => a.label),
    series: [{ name: data.name, values: data.axes.map((a) => a.percentile), notes: data.axes.map((a) => `${axisValue(a)} ${a.unit}`) }],
    footer: 'Higher is better. Scoring includes finishing luck. Source: NHL data, expected goals from our own model.',
  }
  return (
    <section>
      <h2>Scouting card</h2>
      <p className="sub">
        How {data.name} ranks among {data.peer_count} {data.peer_group} this season, as percentiles (the outer ring is the
        best in the league; Defense is scored so that fewer expected goals against is better).
        {data.small_sample && <> Only {data.games_played} GP so far, fewer than the {data.min_gp} used as a peer cutoff, so treat this as early.</>}
      </p>
      <div className="scout">
        <figure className="chart scout-radar">
          <Radar series={[{ id: playerId, slot: 1, name: data.name, axes: data.axes }]} />
        </figure>
        <div className="scout-side">
          <p>
            <strong>Strengths:</strong> {data.strengths.length ? list(data.strengths) : 'none stand out'}.<br />
            <strong>Weaknesses:</strong> {data.weaknesses.length ? list(data.weaknesses) : 'none stand out'}.
          </p>
          <AxisTable data={data} />
          <p className="def-foot">
            * Scoring includes finishing luck and teammates' shooting; see the luck panel. Hits and shot blocking describe
            style, not quality, so they are left out of the strengths and weaknesses. Speed needs NHL EDGE data.
          </p>
          <ShareButtons card={card} filename={`${data.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-scouting.png`} />
        </div>
      </div>
    </section>
  )
}

/** Compare-page overlay of up to three skaters on one radar. Percentiles are within each player's own role. */
export function ScoutingCompare({ players }) {
  const [byId, setById] = useState({})
  useEffect(() => {
    players.filter((p) => !(p.id in byId)).forEach((p) => {
      setById((m) => ({ ...m, [p.id]: null }))
      fetch(`/api/skaters/${p.id}/scouting`)
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => setById((m) => ({ ...m, [p.id]: d })))
        .catch(() => {})
    })
  }, [players, byId])

  const loaded = players
    .map((p) => ({ id: p.id, slot: p.slot, name: byId[p.id]?.name ?? p.name, data: byId[p.id] }))
    .filter((p) => p.data && p.data.axes.some((a) => a.percentile != null))
  if (loaded.length === 0) return null
  const series = loaded.map((p) => ({ id: p.id, slot: p.slot, name: p.name, axes: p.data.axes }))
  const mixed = new Set(loaded.map((p) => p.data.peer_group)).size > 1
  const card = {
    radar: true,
    title: loaded.map((p) => p.name).join(' vs '),
    subtitle: 'Scouting percentiles this season',
    labels: series[0].axes.map((a) => a.label),
    series: series.map((s) => ({ name: s.name, values: s.axes.map((a) => a.percentile) })),
    footer: 'Higher is better. Percentiles are within each player\'s own role (forwards or defensemen).',
  }
  return (
    <>
      <h2>Scouting cards (this season)</h2>
      <p className="sub">
        Percentile among same-role skaters on nine measures; the outer ring is the best in the league.
        {mixed && ' These players are in different roles, so each is ranked against his own.'}
      </p>
      <div className="scout">
        <figure className="chart scout-radar">
          <ul className="legend">
            {series.map((s) => <li key={s.id}><i className={`key solid cmp-key-${s.slot}`} /> {s.name}</li>)}
          </ul>
          <Radar series={series} />
        </figure>
        <div className="scout-side">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="left">Percentile</th>
                  {series.map((s) => <th key={s.id}><i className={`key box cmp-box-${s.slot}`} /> {s.name}</th>)}
                </tr>
              </thead>
              <tbody>
                {series[0].axes.map((a, i) => (
                  <tr key={a.key} title={a.note}>
                    <td className="left">{a.label}</td>
                    {series.map((s) => <td key={s.id}>{ordinal(s.axes[i].percentile)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ShareButtons card={card} filename="scouting-compare.png" />
        </div>
      </div>
    </>
  )
}
