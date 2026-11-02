import { useEffect, useState } from 'react'
import { H, PAD, Rink, S, W, px, py } from './ShotMap.jsx'
import { LANE_LABEL, RANGE_LABEL, gloveSign, signed, zoneCentre, zonePolygon, zoneStrength } from '../goalieZones.js'
import { describe } from '../glossary.js'
import { seasonLabel } from '../career.js'

const pct = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))

function useZones(id, span) {
  const key = `${id}/${span}`
  const [result, setResult] = useState({ key: null, data: null })
  useEffect(() => {
    let ignore = false
    fetch(`/api/goalies/${id}/zones?span=${span}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setResult({ key, data }))
      .catch(() => !ignore && setResult({ key, data: null }))
    return () => { ignore = true }
  }, [id, span, key])
  return result.key === key ? result.data : null
}

// "22-23 +2.1, 23-24 -0.4": a zone's result each season, so a repeat weakness stands apart from a one-year blip.
const bySeason = (m) => Object.entries(m ?? {}).map(([sid, v]) => `${seasonLabel(Number(sid)).replace(/^20/, '').replace('-20', '-')} ${signed(v)}`).join(', ')

const zoneName = (z) => `${z.range === 'close' ? 'Close' : z.range === 'mid' ? 'Mid-range' : 'Long-range'}, ${LANE_LABEL[z.lane].toLowerCase()}`

function ZoneMap({ data }) {
  const sign = gloveSign(data.catches)
  const sideSign = { glove: sign, blocker: -sign, middle: 1 }
  const outline = { x: PAD, y: py(100), w: 85 * S, h: py(25) - py(100) }
  const summary = data.zones
    .map((z) => `${zoneName(z)}: ${z.shots} shots, ${signed(z.gsax)} goals saved above average`)
    .join('; ')
  return (
    <figure className="chart zonemap">
      <figcaption>
        <h3>Goals saved above average, by zone</h3>
        <ul className="legend">
          <li><i className="key box zm-good" /> Fewer goals than average</li>
          <li><i className="key box zm-bad" /> More goals than average</li>
          <li><i className="key box zm-none" /> Under {data.min_zone_shots} shots</li>
        </ul>
      </figcaption>
      <div className="plot" style={{ maxWidth: W }}>
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Goalie zone map. ${summary}`}>
          <defs>
            <clipPath id="zm-clip"><rect x={outline.x} y={outline.y} width={outline.w} height={outline.h} /></clipPath>
          </defs>
          <Rink />
          <g clipPath="url(#zm-clip)">
            {data.zones.map((z) => {
              const pts = zonePolygon(z.range, z.lane, sideSign[z.lane]).map((p) => `${px(-p.y).toFixed(1)},${py(p.x).toFixed(1)}`).join(' ')
              const cls = !z.graded ? 'zm-none' : z.gsax >= 0 ? 'zm-good' : 'zm-bad'
              return (
                <polygon key={`${z.range}-${z.lane}`} points={pts} className={`zm-zone ${cls}${z.flag ? ' zm-flag' : ''}`}
                  style={z.graded ? { fillOpacity: 0.08 + 0.5 * zoneStrength(z.z) } : undefined}>
                  <title>{`${zoneName(z)}: ${z.shots} shots, ${z.goals} goals, ${z.xg.toFixed(1)} expected, ${signed(z.gsax)}`}</title>
                </polygon>
              )
            })}
          </g>
          {data.zones.map((z) => {
            const c = zoneCentre(z.range, z.lane, sideSign[z.lane])
            return (
              <text key={`t-${z.range}-${z.lane}`} x={px(-c.y)} y={py(c.x)} textAnchor="middle" className="zm-text">
                <tspan x={px(-c.y)} dy="-0.2em" className="zm-gsax">{z.shots ? signed(z.gsax) : '–'}</tspan>
                <tspan x={px(-c.y)} dy="1.3em" className="zm-n">{z.shots} shots</tspan>
              </text>
            )
          })}
        </svg>
      </div>
      <p className="def-foot">
        Seen from the shooter's end, with the net at the top. Glove side is on the {sign < 0 ? 'right' : 'left'} of the picture
        ({data.catches ? `he catches ${data.catches}` : 'catching hand unknown, assumed left'}). A thick outline marks a gap too big to be
        chance (about 2 standard deviations).
      </p>
    </figure>
  )
}

function GroupTable({ title, rows, seasons = false }) {
  if (!rows.length) return null
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="left">{title}</th><th>Shots</th><th>Goals</th><th>Expected</th>
            <th title={describe('GSAx')}>GSAx</th><th title={describe('Sv%')}>Sv%</th><th title={describe('xSv%')}>xSv%</th>
            {seasons && <th className="left">By season</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label ?? `${r.range}-${r.lane}`} className={r.flag ? 'zm-row-flag' : undefined}>
              <td className="left">{r.label ?? zoneName(r)}</td>
              <td>{r.shots}</td><td>{r.goals}</td><td>{r.xg.toFixed(1)}</td>
              <td className="accent">{signed(r.gsax)}</td><td>{pct(r.sv_pct)}</td><td>{pct(r.exp_sv_pct)}</td>
              {seasons && <td className="left muted">{bySeason(r.by_season)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const sentence = (h) => {
  const { worst, best } = h
  const where = (z) => `${zoneName(z).toLowerCase()} (${z.shots} shots)`
  const parts = []
  if (worst.gsax < 0) parts.push(`Most leaky: ${where(worst)}, ${signed(worst.gsax)} goals against an average goalie`)
  if (best.gsax > 0) parts.push(`strongest: ${where(best)}, ${signed(best.gsax)}`)
  return parts.join('; ')
}

export default function GoalieZones({ playerId }) {
  const [span, setSpan] = useState('all')
  const data = useZones(playerId, span)
  if (!data || (data.total.shots === 0 && span === 'all')) return null
  const flagged = data.zones.filter((z) => z.flag)
  const many = data.seasons.length > 1
  return (
    <section>
      <h2>Where he's beaten</h2>
      <p className="sub">
        Goals allowed against what an average goalie allows on similar shots from the same spot
        ({data.total.shots} shots on goal over {data.seasons.length === 1 ? seasonLabel(data.seasons[0]) : `${data.seasons.length} seasons (${seasonLabel(data.seasons[0])} to ${seasonLabel(data.seasons[data.seasons.length - 1])})`},
        empty-net shots left out). The NHL feed has no shot height or net location, so a zone is where the shot came
        from, not where it went in. Even a few seasons leave only a few hundred shots in a zone, so treat anything
        unflagged as a lean at most{many && ', and look for a gap that shows up in most seasons in the table'}.
      </p>
      <div className="controls">
        <label>Show{' '}
          <select value={span} onChange={(e) => setSpan(e.target.value)} aria-label="Seasons">
            <option value="all">All seasons with shot locations</option>
            <option value="current">This season only</option>
          </select>
        </label>
      </div>
      {data.headline && <p><strong>{sentence(data.headline)}.</strong>{flagged.length === 0 && ' No zone is far enough from average to rule out chance.'}</p>}
      <ZoneMap data={data} />
      <GroupTable title="Zone" rows={data.zones.filter((z) => z.shots)} seasons={many} />
      <GroupTable title="Shot type" rows={data.shot_types} />
      <GroupTable title="Situation" rows={data.situations} />
      <p className="def-foot">
        Expected goals come from our xG model scaled so that the league sits at zero in each zone, shot type and situation,
        which means the totals here can differ slightly from the GSAx in the shots section above.
      </p>
    </section>
  )
}
