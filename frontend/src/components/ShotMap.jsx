import { useMemo, useState } from 'react'

const S = 7 // pixels per foot
const PAD = 8
const W = 85 * S + PAD * 2
const H = 76 * S + PAD * 2

// Rink coordinates (feet, attacking goal at x = +89) -> SVG pixels, goal at the top of the picture.
const px = (y) => PAD + (y + 42.5) * S
const py = (x) => PAD + (100 - x) * S

const KIND_LABEL = { goal: 'Goal', shot: 'Shot on goal', miss: 'Missed', block: 'Blocked' }
const STRENGTHS = [['all', 'All strengths'], ['ev', 'Even strength'], ['pp', 'Power play'], ['sh', 'Short-handed']]
const PERIOD_LABEL = { 1: '1st period', 2: '2nd period', 3: '3rd period', 4: 'Overtime' }
const fmtDate = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
const clock = (sec) => `P${Math.min(4, Math.floor((sec - 1) / 1200) + 1) === 4 ? 'OT' : Math.floor((sec - 1) / 1200) + 1} ${Math.floor(((sec - 1) % 1200 + 1) / 60)}:${String(((sec - 1) % 1200 + 1) % 60).padStart(2, '0')}`

function Rink() {
  const corner = 28 * S
  const left = PAD, right = PAD + 85 * S, top = py(100), bottom = py(25)
  return (
    <g className="rink">
      {/* boards: rounded at the end wall, open toward the neutral zone */}
      <path
        d={`M${left},${bottom} L${left},${top + corner} Q${left},${top} ${left + corner},${top} L${right - corner},${top} Q${right},${top} ${right},${top + corner} L${right},${bottom}`}
        className="rink-boards"
      />
      <line x1={left} x2={right} y1={bottom} y2={bottom} className="rink-blue" />
      <line x1={left} x2={right} y1={py(89)} y2={py(89)} className="rink-red" />
      {/* crease and net */}
      <path d={`M${px(-6)},${py(89)} A${6 * S},${6 * S} 0 0 0 ${px(6)},${py(89)}`} className="rink-crease" />
      <rect x={px(-3)} y={py(92)} width={6 * S} height={3 * S} className="rink-net" />
      {/* faceoff circles in the attacking zone */}
      {[-22, 22].map((y) => (
        <g key={y}>
          <circle cx={px(y)} cy={py(69)} r={15 * S} className="rink-circle" />
          <circle cx={px(y)} cy={py(69)} r={S} className="rink-dot" />
        </g>
      ))}
    </g>
  )
}

/**
 * Half-rink shot map. Marker size shows expected goals; shape/fill shows the outcome, so color
 * is never the only cue. `shots` rows need x, y, kind and (optionally) xg.
 */
export default function ShotMap({ shots, caption }) {
  const [kinds, setKinds] = useState({ goal: true, shot: true, miss: true, block: false })
  const [strength, setStrength] = useState('all')
  const [period, setPeriod] = useState('all')
  const [hover, setHover] = useState(null)

  // Only the periods these shots span (a single game has three or four; a season of games has all).
  const periods = useMemo(() => [...new Set(shots.map((s) => Math.min(s.period, 4)))].filter((p) => PERIOD_LABEL[p]).sort(), [shots])
  const visible = useMemo(
    () => shots.filter((s) => kinds[s.kind] && (strength === 'all' || s.strength === strength)
      && (period === 'all' || Math.min(s.period, 4) === Number(period))),
    [shots, kinds, strength, period],
  )
  // Draw big/obvious things last so goals sit on top.
  const drawn = useMemo(() => {
    const order = { block: 0, miss: 1, shot: 2, goal: 3 }
    return [...visible].sort((a, b) => order[a.kind] - order[b.kind])
  }, [visible])

  const xgSum = visible.reduce((t, s) => t + (s.xg ?? 0), 0)
  const goals = visible.filter((s) => s.kind === 'goal').length
  const radius = (s) => (s.xg == null ? 3.5 : 4 + 22 * s.xg)

  return (
    <figure className="chart shotmap">
      <figcaption>
        <h3>{caption}</h3>
        <ul className="legend">
          <li><svg width="14" height="14"><circle cx="7" cy="7" r="5" className="m-goal" /></svg> Goal</li>
          <li><svg width="14" height="14"><circle cx="7" cy="7" r="5" className="m-shot" /></svg> Shot on goal</li>
          <li><svg width="14" height="14"><path d="M3,3 L11,11 M11,3 L3,11" className="m-miss" /></svg> Missed</li>
          <li><svg width="14" height="14"><circle cx="7" cy="7" r="2.5" className="m-block" /></svg> Blocked</li>
        </ul>
      </figcaption>

      <div className="shot-controls">
        {Object.entries(KIND_LABEL).map(([k, label]) => (
          <label key={k} className="inline-check">
            <input type="checkbox" checked={kinds[k]} onChange={(e) => setKinds({ ...kinds, [k]: e.target.checked })} /> {label}
          </label>
        ))}
        <select value={strength} onChange={(e) => setStrength(e.target.value)} aria-label="Strength">
          {STRENGTHS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        {periods.length > 1 && (
          <select value={period} onChange={(e) => setPeriod(e.target.value)} aria-label="Period">
            <option value="all">All periods</option>
            {periods.map((p) => <option key={p} value={p}>{PERIOD_LABEL[p]}</option>)}
          </select>
        )}
        <span className="muted">
          {visible.length} attempts · {goals} goals · {xgSum.toFixed(1)} xG
        </span>
      </div>

      <div className="plot" style={{ maxWidth: W }}>
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${caption}: ${visible.length} shot attempts`} onPointerLeave={() => setHover(null)}>
          <Rink />
          {drawn.map((s) => {
            const cx = px(s.y), cy = py(s.x)
            const r = radius(s)
            const common = { onPointerEnter: () => setHover(s) }
            return (
              <g key={`${s.game_id}-${s.event_id}`} {...common}>
                <circle cx={cx} cy={cy} r={Math.max(r, 9)} fill="transparent" />
                {s.kind === 'goal' && <circle cx={cx} cy={cy} r={r} className="m-goal" />}
                {s.kind === 'shot' && <circle cx={cx} cy={cy} r={r} className="m-shot" />}
                {s.kind === 'miss' && <path d={`M${cx - 4},${cy - 4} L${cx + 4},${cy + 4} M${cx + 4},${cy - 4} L${cx - 4},${cy + 4}`} className="m-miss" />}
                {s.kind === 'block' && <circle cx={cx} cy={cy} r="2.5" className="m-block" />}
              </g>
            )
          })}
        </svg>
        {hover && (
          <div
            className={`tip ${px(hover.y) / W > 0.55 ? 'flip' : ''}`}
            style={{ left: `${(px(hover.y) / W) * 100}%`, top: `${(py(hover.x) / H) * 100}%` }}
          >
            <div className="tip-head">{fmtDate(hover.game_date)} vs {hover.opponent} · {clock(hover.time_sec)}</div>
            <div className="tip-row"><strong>{KIND_LABEL[hover.kind]}</strong>{hover.shot_type ? ` · ${hover.shot_type}` : ''}{hover.rebound ? ' · rebound' : ''}</div>
            <div className="tip-row">{hover.distance?.toFixed(0)} ft from the net{hover.xg != null ? ` · ${(hover.xg * 100).toFixed(1)}% xG` : ''}</div>
          </div>
        )}
      </div>
      <p className="axis-note">Marker size = chance quality (xG). Blocked shots are drawn where they were taken.</p>
    </figure>
  )
}
