import { useEffect, useRef, useState } from 'react'

const mmss = (sec) => `${Math.floor(sec / 60)}:${String(Math.round(sec) % 60).padStart(2, '0')}`
const periodOf = (sec) => Math.min(Math.floor(Math.max(sec - 1, 0) / 1200) + 1, 4)
const clock = (sec) => `${periodOf(sec) === 4 ? 'OT' : `P${periodOf(sec)}`} ${mmss(((Math.max(sec - 1, 0)) % 1200) + 1)}`
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
 * Cumulative expected goals for both teams across the game. Each step up is a shot (taller = better
 * chance), dots are goals. The higher line created the better chances, whatever the score says.
 */
export function XgFlow({ shots, goals, away, home }) {
  const [ref, W] = useWidth()
  const H = 280, M = { l: 40, r: 84, t: 14, b: 30 }
  const PW = W - M.l - M.r, PH = H - M.t - M.b
  const attempts = shots.filter((s) => s.period <= 4)
  const length = Math.max(3600, ...attempts.map((s) => s.time_sec))
  const axisEnd = length > 3600 ? Math.ceil(length / 60) * 60 : 3600

  const lines = [away, home].map((team, i) => {
    let total = 0
    const pts = [[0, 0]]
    for (const s of attempts.filter((x) => x.team === team)) {
      pts.push([s.time_sec, total])
      total += s.xg ?? 0
      pts.push([s.time_sec, total])
    }
    pts.push([axisEnd, total])
    return { team, slot: i + 1, pts, total }
  })
  const top = Math.max(1, Math.ceil(Math.max(...lines.map((l) => l.total)) * 2) / 2)
  const x = (t) => M.l + (t / axisEnd) * PW
  const y = (v) => M.t + PH - (v / top) * PH
  const ticks = Array.from({ length: Math.round(top * 2) + 1 }, (_, i) => i / 2)

  const goalDots = goals.filter((g) => g.period <= 4).map((g) => {
    const line = lines.find((l) => l.team === g.team)
    if (!line) return null
    const cum = attempts.filter((s) => s.team === g.team && s.time_sec <= g.time_sec).reduce((t, s) => t + (s.xg ?? 0), 0)
    return { ...g, slot: line.slot, cum }
  }).filter(Boolean)

  // End labels, nudged apart when the teams finish close together.
  const ends = lines.map((l) => ({ ...l, ly: y(l.total) })).sort((a, b) => a.ly - b.ly)
  if (ends[1].ly - ends[0].ly < 14) ends[1].ly = ends[0].ly + 14

  return (
    <figure className="chart wide">
      <figcaption>
        <h3>Expected goals flow</h3>
        <ul className="legend">
          {lines.map((l) => <li key={l.team}><i className={`key solid cmp-key-${l.slot}`} /> {l.team}</li>)}
          <li><i className="key box" style={{ borderRadius: '50%' }} /> Goal</li>
        </ul>
      </figcaption>
      <div className="plot" ref={ref}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Cumulative expected goals by game time">
          {ticks.map((v) => (
            <g key={v}>
              <line x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} className="grid" />
              <text x={M.l - 8} y={y(v)} dy="0.32em" textAnchor="end" className="axis">{v.toFixed(1)}</text>
            </g>
          ))}
          {periodTicks(axisEnd).map((t) => (
            <g key={t}>
              <line x1={x(t)} x2={x(t)} y1={M.t} y2={M.t + PH} className="grid" strokeDasharray={t === 0 ? undefined : '3 3'} />
              <text x={x(t)} y={H - 8} textAnchor="middle" className="axis">{t / 60}′</text>
            </g>
          ))}
          {lines.map((l) => (
            <path key={l.team} d={l.pts.map(([t, v], i) => `${i ? 'L' : 'M'}${x(t).toFixed(1)},${y(v).toFixed(1)}`).join(' ')}
              className={`cmp-line cmp-${l.slot}`} />
          ))}
          {goalDots.map((g, i) => (
            <circle key={i} cx={x(g.time_sec)} cy={y(g.cum)} r={5} className={`cmp-dot cmp-fill-${g.slot}`}>
              <title>{`${g.team} goal · ${g.scorer} · ${clock(g.time_sec)}${g.xg != null ? ` · ${(g.xg * 100).toFixed(0)}% xG` : ''}`}</title>
            </circle>
          ))}
          {ends.map((l) => (
            <text key={l.team} x={W - M.r + 8} y={l.ly} dy="0.32em" className="end-label">{l.team} {l.total.toFixed(2)}</text>
          ))}
        </svg>
      </div>
      <p className="axis-note">Game minute · cumulative expected goals. Shots only; empty-net and shootout attempts included only if the model scored them.</p>
    </figure>
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
          {rows.map(([p, extra], i) => {
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
