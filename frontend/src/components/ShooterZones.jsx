import { useEffect, useState } from 'react'
import { H, PAD, Rink, S, W, px, py } from './ShotMap.jsx'
import { signed, zoneCentre, zonePolygon, zoneStrength } from '../goalieZones.js'
import { seasonLabel } from '../career.js'

const LANE_NAME = { left: 'left side', middle: 'middle', right: 'right side' }
const RANGE_NAME = { close: 'Close', mid: 'Mid-range', long: 'Long-range' }
const zoneName = (z) => `${RANGE_NAME[z.range]}, ${LANE_NAME[z.lane]}`
const pct0 = (v) => `${Math.round(v * 100)}%`

function useZones(id, span, strength) {
  const key = `${id}/${span}/${strength}`
  const [result, setResult] = useState({ key: null, data: null })
  useEffect(() => {
    let ignore = false
    fetch(`/api/skaters/${id}/zones?span=${span}&strength=${strength}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setResult({ key, data }))
      .catch(() => !ignore && setResult({ key, data: null }))
    return () => { ignore = true }
  }, [id, span, strength, key])
  return result.key === key ? result.data : null
}

// "22-23 +2.1, 23-24 -0.4": a zone's result each season, so a repeat strength stands apart from one hot year.
const bySeason = (m) => Object.entries(m ?? {}).map(([sid, v]) => `${seasonLabel(Number(sid)).replace(/^20/, '').replace('-20', '-')} ${signed(v)}`).join(', ')

function ZoneMap({ data }) {
  // Shooter's end: his left is on the left of the picture. Rink y is positive on the shooter's left, and px() draws positive y to the
  // right, so y is mirrored on the way to the screen (the rink is symmetrical, so nothing else changes).
  const sideSign = { left: 1, middle: 1, right: -1 }
  const outline = { x: PAD, y: py(100), w: 85 * S, h: py(25) - py(100) }
  const summary = data.zones.map((z) => `${zoneName(z)}: ${pct0(z.share)} of his attempts, ${signed(z.gsax)} goals against expected`).join('; ')
  return (
    <figure className="chart zonemap">
      <figcaption>
        <h3>Where he shoots, and what it is worth</h3>
        <ul className="legend">
          <li><i className="key box zm-good" /> More goals than expected</li>
          <li><i className="key box zm-bad" /> Fewer goals than expected</li>
          <li><i className="key box zm-none" /> Under {data.min_zone_attempts} attempts</li>
        </ul>
      </figcaption>
      <div className="plot" style={{ maxWidth: W }}>
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Shooter zone map. ${summary}`}>
          <defs>
            <clipPath id="sz-clip"><rect x={outline.x} y={outline.y} width={outline.w} height={outline.h} /></clipPath>
          </defs>
          <Rink />
          <g clipPath="url(#sz-clip)">
            {data.zones.map((z) => {
              const pts = zonePolygon(z.range, z.lane, sideSign[z.lane]).map((p) => `${px(-p.y).toFixed(1)},${py(p.x).toFixed(1)}`).join(' ')
              const cls = !z.graded ? 'zm-none' : z.gsax >= 0 ? 'zm-good' : 'zm-bad'
              return (
                <polygon key={`${z.range}-${z.lane}`} points={pts} className={`zm-zone ${cls}${z.flag ? ' zm-flag' : ''}`}
                  style={z.graded ? { fillOpacity: 0.08 + 0.5 * zoneStrength(z.z) } : undefined}>
                  <title>{`${zoneName(z)}: ${z.attempts} attempts (${pct0(z.share)} of his, ${pct0(z.league_share)} for the league), ${z.goals} goals, ${z.xg.toFixed(1)} expected, ${signed(z.gsax)}`}</title>
                </polygon>
              )
            })}
          </g>
          {data.zones.map((z) => {
            const c = zoneCentre(z.range, z.lane, sideSign[z.lane])
            return (
              <text key={`t-${z.range}-${z.lane}`} x={px(-c.y)} y={py(c.x)} textAnchor="middle" className="zm-text">
                <tspan x={px(-c.y)} dy="-0.2em" className="zm-gsax">{z.attempts ? signed(z.gsax) : '–'}</tspan>
                <tspan x={px(-c.y)} dy="1.3em" className="zm-n">{pct0(z.share)} of shots</tspan>
              </text>
            )
          })}
        </svg>
      </div>
      <p className="def-foot">
        Seen from the shooter's end, with the net at the top. The big number is goals minus expected goals in the zone; the small one is the
        share of his attempts taken there. A thick outline marks a gap too big to be chance (about 2 standard deviations).
      </p>
    </figure>
  )
}

function GroupTable({ title, rows, zones = false, seasons = false }) {
  if (!rows.length) return null
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="left">{title}</th>
            <th title="Shot attempts that were on goal, missed, or scored (blocked shots are not counted)">Attempts</th>
            {zones && <><th title="Share of his attempts taken from this zone">His share</th><th title="Share of all players' attempts taken from this zone">League</th></>}
            <th>Goals</th><th title="Expected goals from the quality of the shots">xG</th>
            <th title="Goals minus expected goals compared with an average shooter from the same spot; positive is good">Goals vs xG</th>
            {seasons && <th className="left">By season</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label ?? `${r.range}-${r.lane}`} className={r.flag ? 'zm-row-flag' : undefined}>
              <td className="left">{r.label ?? zoneName(r)}</td>
              <td>{r.attempts}</td>
              {zones && <><td>{pct0(r.share)}</td><td>{pct0(r.league_share)}</td></>}
              <td>{r.goals}</td><td>{r.xg.toFixed(1)}</td><td className="accent">{signed(r.gsax)}</td>
              {seasons && <td className="left muted">{bySeason(r.by_season)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const where = (z) => `${zoneName(z).toLowerCase()} (${z.attempts} attempts)`

function sentence(h) {
  const parts = []
  if (h.favours.share - h.favours.league_share >= 0.04) {
    parts.push(`Shoots from ${zoneName(h.favours).toLowerCase()} far more than most (${pct0(h.favours.share)} of his attempts against ${pct0(h.favours.league_share)} league-wide)`)
  }
  if (h.best.gsax > 0) parts.push(`best finishing: ${where(h.best)}, ${signed(h.best.gsax)} against an average shooter`)
  if (h.worst.gsax < 0) parts.push(`worst: ${where(h.worst)}, ${signed(h.worst.gsax)}`)
  return parts.join('; ')
}

export default function ShooterZones({ playerId }) {
  const [span, setSpan] = useState('all')
  const [strength, setStrength] = useState('all')
  const data = useZones(playerId, span, strength)
  if (!data || (data.total.attempts === 0 && span === 'all' && strength === 'all')) return null
  const flagged = data.zones.filter((z) => z.flag)
  const many = data.seasons.length > 1
  const span_ = data.seasons.length === 0 ? '' : data.seasons.length === 1
    ? seasonLabel(data.seasons[0]) : `${data.seasons.length} seasons (${seasonLabel(data.seasons[0])} to ${seasonLabel(data.seasons[data.seasons.length - 1])})`
  return (
    <section>
      <h2>Where he shoots from</h2>
      <p className="sub">
        His shot attempts by zone ({data.total.attempts} unblocked attempts{span_ && ` over ${span_}`}, empty-net shots left out) and the goals
        he scores against what an average shooter scores from similar shots in the same spot. Goals above expected here also reflect
        his shot, not only luck, since the model knows nothing about the shooter, but a few dozen attempts in a zone is still a small
        sample: treat anything unflagged as a lean{many && ', and look for a zone that is positive in most seasons'}.
      </p>
      <div className="controls">
        <label>Show{' '}
          <select value={span} onChange={(e) => setSpan(e.target.value)} aria-label="Seasons">
            <option value="all">All seasons with shot locations</option>
            <option value="current">This season only</option>
          </select>
        </label>
        <label>Strength{' '}
          <select value={strength} onChange={(e) => setStrength(e.target.value)} aria-label="Strength">
            <option value="all">All strengths</option>
            <option value="ev">Even strength</option>
            <option value="pp">Power play</option>
          </select>
        </label>
      </div>
      {data.total.attempts === 0 ? <p className="status">No attempts in this selection.</p> : (
        <>
          {data.headline && <p><strong>{sentence(data.headline)}.</strong>{flagged.length === 0 && ' No zone is far enough from average to rule out chance.'}</p>}
          <ZoneMap data={data} />
          <GroupTable title="Zone" rows={data.zones.filter((z) => z.attempts)} zones seasons={many} />
          <GroupTable title="Shot type" rows={data.shot_types} />
          <GroupTable title="Situation" rows={data.situations} />
          <p className="def-foot">
            Expected goals come from our xG model, scaled so each season matches its real goals and then so the league sits at zero in
            each zone, shot type and situation. A player who finishes well everywhere shows a positive number in every zone.
          </p>
        </>
      )}
    </section>
  )
}
