export const mmss = (sec) => `${Math.floor(sec / 60)}:${String(Math.round(sec) % 60).padStart(2, '0')}`
export const periodOf = (sec) => Math.min(Math.floor(Math.max(sec - 1, 0) / 1200) + 1, 4)
export const clock = (sec) => `${periodOf(sec) === 4 ? 'OT' : `P${periodOf(sec)}`} ${mmss(((Math.max(sec - 1, 0)) % 1200) + 1)}`

export const FIVE_ON_FIVE = '1551' // situation code: away goalie, away skaters, home skaters, home goalie

export const goalTip = (g) => `${g.team} goal · ${g.scorer} · ${clock(g.time_sec)}${g.xg != null ? ` · ${(g.xg * 100).toFixed(0)}% xG` : ''}`

/** Where the time axis ends: 60 minutes, or the end of overtime (which runs short of a full period). */
export const gameEnd = (attempts) => {
  const length = Math.max(3600, ...attempts.map((s) => s.time_sec))
  return length > 3600 ? Math.ceil(length / 60) * 60 : 3600
}

/** What the xG flow chart draws: cumulative expected goals per team and a dot per goal. */
export function xgModel({ shots, goals, away, home }) {
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
  const dots = goals.filter((g) => g.period <= 4).map((g) => ({
    t: g.time_sec, slot: g.team === away ? 1 : 2, tip: goalTip(g),
    v: attempts.filter((s) => s.team === g.team && s.time_sec <= g.time_sec).reduce((t, s) => t + (s.xg ?? 0), 0),
  }))
  return {
    axisEnd, lines, dots,
    domain: { min: 0, max: top, ticks: Array.from({ length: Math.round(top * 2) + 1 }, (_, i) => i / 2) },
    fmt: (v) => v.toFixed(1),
  }
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

