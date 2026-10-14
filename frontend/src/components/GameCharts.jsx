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

const FIVE_ON_FIVE = '1551' // situation code: away goalie, away skaters, home skaters, home goalie

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

const goalTip = (g) => `${g.team} goal · ${g.scorer} · ${clock(g.time_sec)}${g.xg != null ? ` · ${(g.xg * 100).toFixed(0)}% xG` : ''}`
const gameEnd = (attempts) => {
  const length = Math.max(3600, ...attempts.map((s) => s.time_sec))
  return length > 3600 ? Math.ceil(length / 60) * 60 : 3600
}

/**
 * Cumulative expected goals for both teams across the game. Each step up is a shot (taller = better
 * chance), dots are goals. The higher line created the better chances, whatever the score says.
 */
export function XgFlow({ shots, goals, away, home }) {
  const attempts = shots.filter((s) => s.period <= 4)
  const axisEnd = gameEnd(attempts)
  const lines = [away, home].map((team, i) => {
    let total = 0
    const pts = [[0, 0]]
    for (const s of attempts.filter((x) => x.team === team)) {
      pts.push([s.time_sec, total])
      total += s.xg ?? 0
      pts.push([s.time_sec, total])
    }
    pts.push([axisEnd, total])
    return { key: team, label: team, slot: i + 1, pts, endLabel: `${team} ${total.toFixed(2)}`, total }
  })
  const top = Math.max(1, Math.ceil(Math.max(...lines.map((l) => l.total)) * 2) / 2)
  const dots = goals.filter((g) => g.period <= 4).map((g) => {
    const slot = g.team === away ? 1 : 2
    const v = attempts.filter((s) => s.team === g.team && s.time_sec <= g.time_sec).reduce((t, s) => t + (s.xg ?? 0), 0)
    return { t: g.time_sec, v, slot, tip: goalTip(g) }
  })
  return (
    <FlowChart
      title="Expected goals flow" label="Cumulative expected goals by game time" lines={lines} dots={dots} axisEnd={axisEnd}
      domain={{ min: 0, max: top, ticks: Array.from({ length: Math.round(top * 2) + 1 }, (_, i) => i / 2) }}
      fmt={(v) => v.toFixed(1)}
      note="Game minute · cumulative expected goals. Shots only; empty-net and shootout attempts included only if the model scored them."
    />
  )
}

/**
 * What the Corsi chart draws for a view ('attempts' or 'difference') and strength ('all' or '5v5'):
 * { lines, domain, fmt, dots, note, axisEnd }. Kept separate from the component so it can be tested.
 */
export function corsiModel({ shots, goals, away, home, view, strength }) {
  const attempts = shots.filter((s) => s.period <= 4)
  const axisEnd = gameEnd(attempts)
  const pool = (strength === '5v5' ? attempts.filter((s) => s.situation === FIVE_ON_FIVE) : attempts)
    .slice().sort((a, b) => a.time_sec - b.time_sec)
  const scope = strength === '5v5' ? ' at 5v5' : ' (all strengths)'
  const regGoals = goals.filter((g) => g.period <= 4)

  if (view === 'attempts') {
    const built = [away, home].map((team, i) => {
      let n = 0
      const pts = [[0, 0]]
      for (const s of pool.filter((x) => x.team === team)) {
        pts.push([s.time_sec, n]); n += 1; pts.push([s.time_sec, n])
      }
      pts.push([axisEnd, n])
      return { team, slot: i + 1, pts, n }
    })
    const top = Math.max(10, Math.ceil(Math.max(...built.map((l) => l.n)) / 10) * 10)
    const step = top > 80 ? 20 : top > 40 ? 10 : 5
    return {
      axisEnd,
      lines: built.map((l) => ({ key: l.team, label: l.team, slot: l.slot, pts: l.pts, endLabel: `${l.team} ${l.n}` })),
      domain: { min: 0, max: top, ticks: Array.from({ length: Math.floor(top / step) + 1 }, (_, i) => i * step) },
      fmt: (v) => v,
      dots: regGoals.map((g) => ({
        t: g.time_sec, v: pool.filter((s) => s.team === g.team && s.time_sec <= g.time_sec).length,
        slot: g.team === away ? 1 : 2, tip: goalTip(g),
      })),
      note: `Game minute · cumulative shot attempts${scope}. Dots are goals.`,
    }
  }

  // Running difference: positive means the away team has had more attempts.
  let d = 0
  const pts = [[0, 0]]
  for (const s of pool) {
    pts.push([s.time_sec, d]); d += s.team === away ? 1 : -1; pts.push([s.time_sec, d])
  }
  pts.push([axisEnd, d])
  const lim = Math.max(5, Math.ceil(Math.max(...pts.map(([, v]) => Math.abs(v))) / 5) * 5)
  const step = lim > 30 ? 10 : 5
  const ticks = []
  for (let v = -lim; v <= lim; v += step) ticks.push(v)
  return {
    axisEnd,
    lines: [{ key: 'diff', label: `${away} minus ${home}`, slot: 1, pts, endLabel: `${d > 0 ? '+' : ''}${d} ${d >= 0 ? away : home}` }],
    domain: { min: -lim, max: lim, ticks },
    fmt: (v) => (v > 0 ? `+${v}` : v),
    dots: regGoals.map((g) => ({
      t: g.time_sec, v: pool.filter((s) => s.time_sec <= g.time_sec).reduce((t, s) => t + (s.team === away ? 1 : -1), 0),
      slot: g.team === away ? 1 : 2, tip: goalTip(g),
    })),
    note: `Game minute · ${away} attempts minus ${home} attempts${strength === '5v5' ? ' at 5v5' : ''}. Above the line, ${away} has had more of the puck. Dots are goals.`,
  }
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
