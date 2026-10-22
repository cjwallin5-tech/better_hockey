import { useEffect, useRef, useState } from 'react'
import { clock, corsiModel, mmss, xgModel } from '../gameFlow.js'

const lastName = (full) => full.split(' ').slice(1).join(' ') || full

// Draw at the container's real pixel width so text stays a constant size on any screen.
function useWidth() {
  const ref = useRef(null)
  const [w, setW] = useState(640)
  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setW(Math.max(300, Math.round(e.contentRect.width))))
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}

// Period boundaries and tick labels for a game that runs `length` seconds.
function periodTicks(length) {
  const ticks = []
  for (let t = 0; t <= length; t += 1200) ticks.push(t)
  return ticks
}

/**
 * A cumulative-by-game-time chart for the two teams. lines: [{ key, label, slot, pts: [[t, v]] }];
 * dots: [{ t, v, slot, tip }] drawn on top (goals). domain: { min, max, ticks }.
 */
function FlowChart({ title, label, lines, dots, domain, axisEnd, fmt, legendDot = true, note }) {
  const [ref, W] = useWidth()
  const H = 280, M = { l: 44, r: 96, t: 14, b: 30 }
  const PW = W - M.l - M.r, PH = H - M.t - M.b
  const x = (t) => M.l + (t / axisEnd) * PW
  const y = (v) => M.t + PH - ((v - domain.min) / (domain.max - domain.min)) * PH

  // End labels, nudged apart when the lines finish close together.
  const ends = lines.map((l) => ({ ...l, ly: y(l.pts[l.pts.length - 1][1]) })).sort((a, b) => a.ly - b.ly)
  for (let i = 1; i < ends.length; i += 1) if (ends[i].ly - ends[i - 1].ly < 14) ends[i].ly = ends[i - 1].ly + 14

  return (
    <figure className="chart wide">
      <figcaption>
        <h3>{title}</h3>
        <ul className="legend">
          {lines.map((l) => <li key={l.key}><i className={`key solid cmp-key-${l.slot}`} /> {l.label}</li>)}
          {legendDot && <li><i className="key box" style={{ borderRadius: '50%' }} /> Goal</li>}
        </ul>
      </figcaption>
      <div className="plot" ref={ref}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
          {domain.ticks.map((v) => (
            <g key={v}>
              <line x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} className={v === 0 && domain.min < 0 ? 'cross' : 'grid'} />
              <text x={M.l - 8} y={y(v)} dy="0.32em" textAnchor="end" className="axis">{fmt(v)}</text>
            </g>
          ))}
          {periodTicks(axisEnd).map((t) => (
            <g key={t}>
              <line x1={x(t)} x2={x(t)} y1={M.t} y2={M.t + PH} className="grid" strokeDasharray={t === 0 ? undefined : '3 3'} />
              <text x={x(t)} y={H - 8} textAnchor="middle" className="axis">{t / 60}′</text>
            </g>
          ))}
          {lines.map((l) => (
            <path key={l.key} d={l.pts.map(([t, v], i) => `${i ? 'L' : 'M'}${x(t).toFixed(1)},${y(v).toFixed(1)}`).join(' ')}
              className={`cmp-line cmp-${l.slot}`} />
          ))}
          {dots.map((d, i) => (
            <circle key={i} cx={x(d.t)} cy={y(d.v)} r={5} className={`cmp-dot cmp-fill-${d.slot}`}><title>{d.tip}</title></circle>
          ))}
          {ends.map((l) => (
            <text key={l.key} x={W - M.r + 8} y={l.ly} dy="0.32em" className="end-label">{l.endLabel}</text>
          ))}
        </svg>
      </div>
      <p className="axis-note">{note}</p>
    </figure>
  )
}

/**
 * Cumulative expected goals for both teams across the game. Each step up is a shot (taller = better
 * chance), dots are goals. The higher line created the better chances, whatever the score says.
 */
export function XgFlow({ shots, goals, away, home }) {
  const m = xgModel({ shots, goals, away, home })
  return (
    <FlowChart
      title="Expected goals flow" label="Cumulative expected goals by game time" lines={m.lines} dots={m.dots} axisEnd={m.axisEnd}
      domain={m.domain} fmt={m.fmt}
      note="Game minute · cumulative expected goals. Shots only; empty-net and shootout attempts included only if the model scored them."
    />
  )
}

/**
 * Shot attempts (Corsi: shots on goal, misses and blocks) over the game, for both teams or as the running
 * difference. Attempts are a better read on who had the puck than goals, which are rare.
 */
export function CorsiFlow({ shots, goals, away, home }) {
  const [view, setView] = useState('attempts') // attempts | difference
  const [strength, setStrength] = useState('all') // all | 5v5
  const m = corsiModel({ shots, goals, away, home, view, strength })

  return (
    <>
      <div className="tabs" role="tablist" aria-label="Shot attempt chart options">
        {[['attempts', 'Attempts'], ['difference', 'Difference']].map(([id, label]) => (
          <button key={id} role="tab" aria-selected={view === id} className={view === id ? 'on' : ''} onClick={() => setView(id)}>{label}</button>
        ))}
        <span className="tabs-gap" />
        {[['all', 'All strengths'], ['5v5', '5v5 only']].map(([id, label]) => (
          <button key={id} role="tab" aria-selected={strength === id} className={strength === id ? 'on' : ''} onClick={() => setStrength(id)}>{label}</button>
        ))}
      </div>
      <FlowChart
        title="Shot attempt flow (Corsi)" label="Shot attempts by game time" lines={m.lines} dots={m.dots} axisEnd={m.axisEnd}
        domain={m.domain} fmt={m.fmt} note={m.note}
      />
    </>
  )
}

/** Who was on the ice when: one row per skater, one bar per shift, with goals marked. */
export function ShiftChart({ game, goals, away, home }) {
  const [side, setSide] = useState(away)
  const [state, setState] = useState({ id: null, data: null })
  const [ref, W] = useWidth()

  useEffect(() => {
    let ignore = false
    fetch(`/api/games/${game.game_id}/shifts`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setState({ id: game.game_id, data }))
      .catch(() => !ignore && setState({ id: game.game_id, data: null }))
    return () => { ignore = true }
  }, [game.game_id])

  const data = state.id === game.game_id ? state.data : null
  if (!data || data.players.length === 0) return null

  const ROW = 15, L = 132, R = 14, T = 8, B = 26, GAP = 10
  const mine = data.players.filter((p) => p.team === side)
  const forwards = mine.filter((p) => p.position !== 'D'), defense = mine.filter((p) => p.position === 'D')
  const rows = [...forwards.map((p) => [p, 0]), ...defense.map((p) => [p, GAP])]
  const H = T + rows.length * ROW + GAP + B
  const PW = W - L - R
  const x = (t) => L + (t / data.length_sec) * PW
  const slot = side === away ? 1 : 2

  return (
    <figure className="chart wide">
      <figcaption>
        <h3>Shift chart</h3>
        <div className="tabs" role="tablist">
          {[away, home].map((t) => (
            <button key={t} role="tab" aria-selected={side === t} className={side === t ? 'on' : ''} onClick={() => setSide(t)}>{t}</button>
          ))}
        </div>
      </figcaption>
      <div className="plot" ref={ref}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${side} shifts by game time`}>
          {periodTicks(data.length_sec).map((t) => (
            <g key={t}>
              <line x1={x(t)} x2={x(t)} y1={T} y2={H - B} className="grid" strokeDasharray={t === 0 ? undefined : '3 3'} />
              <text x={x(t)} y={H - 8} textAnchor="middle" className="axis">{t / 60}′</text>
            </g>
          ))}
          {rows.map(([p], i) => {
            const yy = T + i * ROW + (p.position === 'D' ? GAP : 0)
            return (
              <g key={p.player_id}>
                <text x={L - 8} y={yy + ROW / 2} dy="0.32em" textAnchor="end" className="axis">
                  {lastName(p.name)} <tspan opacity="0.6">{p.position ?? ''} {mmss(p.toi_sec)}</tspan>
                </text>
                {p.shifts.map(([s, e], j) => (
                  <rect key={j} x={x(s)} y={yy + 2} width={Math.max(1.5, x(e) - x(s))} height={ROW - 4} rx="1.5" className={`cmp-fill-${slot}`}>
                    <title>{`${p.name} · ${clock(s + 1)}–${mmss(((e - 1) % 1200) + 1)} (${mmss(e - s)})`}</title>
                  </rect>
                ))}
              </g>
            )
          })}
          {goals.map((g, i) => (
            <line key={i} x1={x(g.time_sec)} x2={x(g.time_sec)} y1={T} y2={H - B}
              className={g.team === side ? 'goal-for' : 'goal-against'}>
              <title>{`${g.team} goal · ${g.scorer} · ${clock(g.time_sec)}`}</title>
            </line>
          ))}
        </svg>
      </div>
      <p className="axis-note">
        Each bar is a shift; forwards on top, defensemen below, busiest first. Solid lines are {side} goals, dashed are goals against.
      </p>
    </figure>
  )
}
