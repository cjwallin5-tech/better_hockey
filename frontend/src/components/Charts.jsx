import { useEffect, useRef, useState } from 'react'

const H = 260
const M = { l: 36, r: 16, t: 14, b: 30 }
const PH = H - M.t - M.b

// Draw at the container's real pixel width so text stays a constant size at any card width.
function useWidth() {
  const ref = useRef(null)
  const [w, setW] = useState(480)
  useEffect(() => {
    const el = ref.current
    const ro = new ResizeObserver(([entry]) => setW(Math.max(260, Math.round(entry.contentRect.width))))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}

// Round the axis max up to a "nice" number and pick a tick step that gives ~4-5 ticks.
function niceAxis(max, minStep = 0) {
  const raw = Math.max(max, 1) / 4
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw && s >= minStep)
  const top = Math.ceil(Math.max(max, 1) / step) * step
  const ticks = []
  for (let v = 0; v <= top; v += step) ticks.push(v)
  return { top, ticks }
}

const fmtDate = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

// Shared pointer/keyboard handling: snaps to the nearest of `count` game positions.
function useGameCursor(count, xOf, W) {
  const [idx, setIdx] = useState(null)
  const svgRef = useRef(null)

  const onMove = (e) => {
    const rect = svgRef.current.getBoundingClientRect()
    const vx = ((e.clientX - rect.left) / rect.width) * W
    let best = 0
    for (let i = 1; i < count; i++) {
      if (Math.abs(xOf(i) - vx) < Math.abs(xOf(best) - vx)) best = i
    }
    setIdx(best)
  }
  const onKey = (e) => {
    if (e.key === 'ArrowLeft') setIdx((i) => Math.max(0, (i ?? count) - 1))
    else if (e.key === 'ArrowRight') setIdx((i) => Math.min(count - 1, (i ?? -1) + 1))
    else if (e.key === 'Escape') setIdx(null)
  }
  const handlers = {
    ref: svgRef,
    tabIndex: 0,
    onPointerMove: onMove,
    onPointerLeave: () => setIdx(null),
    onBlur: () => setIdx(null),
    onKeyDown: onKey,
  }
  return [idx, handlers]
}

function Tooltip({ x, W, children }) {
  const left = (x / W) * 100
  return (
    <div className={`tip ${left > 60 ? 'flip' : ''}`} style={{ left: `${left}%` }}>
      {children}
    </div>
  )
}

function YAxis({ ticks, y, W }) {
  return ticks.map((v) => (
    <g key={v}>
      <line x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} className="grid" />
      <text x={M.l - 8} y={y(v)} dy="0.32em" textAnchor="end" className="axis">{v}</text>
    </g>
  ))
}

/**
 * Cumulative points through the season against a straight "pace" line from 0 to the
 * projected season total. `games` must be in chronological order.
 */
export function PaceChart({ games, seasonGames, pace }) {
  const [plotRef, W] = useWidth()
  const PW = W - M.l - M.r
  const n = games.length
  const cum = games.reduce((acc, g, i) => [...acc, (acc[i - 1] ?? 0) + g.points], [])
  const total = cum[n - 1] ?? 0
  const { top, ticks } = niceAxis(Math.max(pace ?? 0, total))

  const x = (g) => M.l + (g / seasonGames) * PW
  const y = (v) => M.t + PH - (v / top) * PH
  const [idx, cursor] = useGameCursor(n, (i) => x(i + 1), W)

  const line = [[0, 0], ...cum.map((v, i) => [i + 1, v])]
    .map(([g, v], i) => `${i ? 'L' : 'M'}${x(g).toFixed(1)},${y(v).toFixed(1)}`)
    .join(' ')
  const paceAt = (g) => (pace == null ? null : (pace * g) / seasonGames)

  const xTicks = [0, 1, 2, 3, 4].map((k) => Math.round((seasonGames * k) / 4))
  const g = idx == null ? null : games[idx]

  return (
    <figure className="chart">
      <figcaption>
        <h3>Points vs. pace</h3>
        <ul className="legend">
          <li><i className="key solid" /> Points</li>
          <li><i className="key dashed" /> Pace line ({pace == null ? '–' : pace.toFixed(1)} pts / {seasonGames} GP)</li>
        </ul>
      </figcaption>
      <div className="plot" ref={plotRef}>
        <svg
          width={W} height={H} viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label="Cumulative points by game compared to the projected pace line"
          {...cursor}
        >
          <YAxis ticks={ticks} y={y} W={W} />
          {xTicks.map((t) => (
            <text key={t} x={x(t)} y={H - 8} textAnchor="middle" className="axis">{t}</text>
          ))}
          {pace != null && (
            <line x1={x(0)} y1={y(0)} x2={x(seasonGames)} y2={y(pace)} className="pace-line" />
          )}
          <path d={line} className="series-line" />
          {n > 0 && <circle cx={x(n)} cy={y(total)} r="4" className="dot" />}
          {g && (
            <g pointerEvents="none">
              <line x1={x(idx + 1)} x2={x(idx + 1)} y1={M.t} y2={M.t + PH} className="cross" />
              <circle cx={x(idx + 1)} cy={y(cum[idx])} r="4.5" className="dot" />
            </g>
          )}
        </svg>
        {g && (
          <Tooltip W={W} x={x(idx + 1)}>
            <div className="tip-head">Game {idx + 1} · {fmtDate(g.game_date)} {g.is_home ? 'vs' : '@'} {g.opponent}</div>
            <div className="tip-row"><i className="key solid" /><strong>{cum[idx]}</strong> points</div>
            {pace != null && (
              <div className="tip-row"><i className="key dashed" /><strong>{paceAt(idx + 1).toFixed(1)}</strong> pace line</div>
            )}
          </Tooltip>
        )}
      </div>
    </figure>
  )
}

/** Points in each game, one bar per game, chronological. */
export function GameBars({ games }) {
  const [plotRef, W] = useWidth()
  const PW = W - M.l - M.r
  const n = games.length
  const maxPts = Math.max(...games.map((g) => g.points), 0)
  const { top, ticks } = niceAxis(Math.max(maxPts, 2), 1) // whole points only
  const slot = PW / Math.max(n, 8)
  const barW = Math.min(slot - 2, 28) // 2px gap between bars
  const x = (i) => M.l + slot * i + slot / 2
  const y = (v) => M.t + PH - (v / top) * PH
  const [idx, cursor] = useGameCursor(n, x, W)
  const step = Math.ceil(n / 10)
  const g = idx == null ? null : games[idx]

  return (
    <figure className="chart">
      <figcaption>
        <h3>Points per game</h3>
      </figcaption>
      <div className="plot" ref={plotRef}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Points scored in each game" {...cursor}>
          <YAxis ticks={ticks} y={y} W={W} />
          {games.map((game, i) => (
            <g key={game.game_id}>
              {game.points > 0 && (
                <rect
                  x={x(i) - barW / 2}
                  y={y(game.points)}
                  width={barW}
                  height={y(0) - y(game.points)}
                  rx="3"
                  className={`game-bar ${i === idx ? 'on' : ''}`}
                />
              )}
              {i % step === 0 && (
                <text x={x(i)} y={H - 8} textAnchor="middle" className="axis">{i + 1}</text>
              )}
            </g>
          ))}
        </svg>
        {g && (
          <Tooltip W={W} x={x(idx)}>
            <div className="tip-head">Game {idx + 1} · {fmtDate(g.game_date)} {g.is_home ? 'vs' : '@'} {g.opponent}</div>
            <div className="tip-row"><i className="key solid" /><strong>{g.points}</strong> points ({g.goals}G {g.assists}A)</div>
            <div className="tip-row"><strong>{g.shots ?? '–'}</strong> shots</div>
          </Tooltip>
        )}
      </div>
      <p className="axis-note">Game number</p>
    </figure>
  )
}

/** Hits and blocked shots in each game: two bars per game, hits on the left. */
export function DefenseBars({ games }) {
  const [plotRef, W] = useWidth()
  const PW = W - M.l - M.r
  const n = games.length
  const maxVal = Math.max(...games.flatMap((g) => [g.hits ?? 0, g.blocked_shots ?? 0]), 0)
  const { top, ticks } = niceAxis(Math.max(maxVal, 2), 1) // whole counts only
  const slot = PW / Math.max(n, 8)
  const barW = Math.min((slot - 4) / 2, 14) // 2px gap between the pair and between games
  const x = (i) => M.l + slot * i + slot / 2
  const y = (v) => M.t + PH - (v / top) * PH
  const [idx, cursor] = useGameCursor(n, x, W)
  const step = Math.ceil(n / 10)
  const g = idx == null ? null : games[idx]

  const bar = (i, offset, value, cls) =>
    value > 0 && (
      <rect
        x={x(i) + offset}
        y={y(value)}
        width={barW}
        height={y(0) - y(value)}
        rx="3"
        className={cls}
      />
    )

  return (
    <figure className="chart wide">
      <figcaption>
        <h3>Hits and blocked shots per game</h3>
        <ul className="legend">
          <li><i className="key box hits" /> Hits</li>
          <li><i className="key box blocks" /> Blocked shots</li>
        </ul>
      </figcaption>
      <div className="plot" ref={plotRef}>
        <svg
          width={W} height={H} viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label="Hits and blocked shots in each game"
          {...cursor}
        >
          <YAxis ticks={ticks} y={y} W={W} />
          {games.map((game, i) => (
            <g key={game.game_id}>
              {i === idx && (
                <rect x={x(i) - slot / 2} y={M.t} width={slot} height={PH} className="hover-band" />
              )}
              {bar(i, -barW - 1, game.hits, 'bar-hits')}
              {bar(i, 1, game.blocked_shots, 'bar-blocks')}
              {i % step === 0 && (
                <text x={x(i)} y={H - 8} textAnchor="middle" className="axis">{i + 1}</text>
              )}
            </g>
          ))}
        </svg>
        {g && (
          <Tooltip W={W} x={x(idx)}>
            <div className="tip-head">Game {idx + 1} · {fmtDate(g.game_date)} {g.is_home ? 'vs' : '@'} {g.opponent}</div>
            <div className="tip-row"><i className="key box hits" /><strong>{g.hits ?? '–'}</strong> hits</div>
            <div className="tip-row"><i className="key box blocks" /><strong>{g.blocked_shots ?? '–'}</strong> blocked shots</div>
            <div className="tip-head tip-sub">{g.takeaways ?? '–'} takeaways · {g.giveaways ?? '–'} giveaways</div>
          </Tooltip>
        )}
      </div>
      <p className="axis-note">Game number</p>
    </figure>
  )
}

// Axis that always includes 0 and may go negative; ticks are rounded to avoid float noise.
function niceRange(min, max) {
  const lo = Math.min(min, 0)
  const hi = Math.max(max, 0)
  const raw = Math.max(hi - lo, 1) / 4
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw)
  const bottom = Math.floor(lo / step) * step
  const top = Math.ceil(hi / step) * step
  const ticks = []
  for (let v = bottom; v <= top + step / 2; v += step) ticks.push(Math.round(v * 100) / 100)
  return { bottom, top, ticks }
}

/**
 * Cumulative goals saved above average over a goalie's games (chronological).
 * Each game's value is shots_against * (1 - league sv%) - goals_against.
 */
export function GsaaChart({ games, leagueSvPct }) {
  const [plotRef, W] = useWidth()
  const PW = W - M.l - M.r
  const n = games.length
  const per = games.map((g) => (g.shots_against ?? 0) * (1 - leagueSvPct) - (g.goals_against ?? 0))
  const cum = per.reduce((acc, v, i) => [...acc, (acc[i - 1] ?? 0) + v], [])
  const { bottom, top, ticks } = niceRange(Math.min(0, ...cum), Math.max(0, ...cum))

  const x = (i) => M.l + (PW * (i + 0.5)) / Math.max(n, 6)
  const y = (v) => M.t + PH - ((v - bottom) / (top - bottom)) * PH
  const [idx, cursor] = useGameCursor(n, x, W)
  const g = idx == null ? null : games[idx]
  const step = Math.ceil(n / 10)

  const line = cum.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')

  return (
    <figure className="chart">
      <figcaption>
        <h3>Goals saved above average (cumulative)</h3>
      </figcaption>
      <div className="plot" ref={plotRef}>
        <svg
          width={W}
          height={H}
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label="Cumulative goals saved above average by game"
          {...cursor}
        >
          <YAxis ticks={ticks} y={y} W={W} />
          <line x1={M.l} x2={W - M.r} y1={y(0)} y2={y(0)} className="zero-line" />
          {games.map((_, i) =>
            i % step === 0 ? (
              <text key={i} x={x(i)} y={H - 8} textAnchor="middle" className="axis">{i + 1}</text>
            ) : null,
          )}
          <path d={line} className="series-line" />
          {cum.map((v, i) => (
            <circle key={i} cx={x(i)} cy={y(v)} r={i === idx ? 4.5 : 3} className="dot" />
          ))}
          {g && (
            <line x1={x(idx)} x2={x(idx)} y1={M.t} y2={M.t + PH} className="cross" pointerEvents="none" />
          )}
        </svg>
        {g && (
          <Tooltip W={W} x={x(idx)}>
            <div className="tip-head">Game {idx + 1} · {fmtDate(g.game_date)} {g.is_home ? 'vs' : '@'} {g.opponent}</div>
            <div className="tip-row"><i className="key solid" /><strong>{cum[idx].toFixed(2)}</strong> cumulative</div>
            <div className="tip-row"><strong>{per[idx] > 0 ? '+' : ''}{per[idx].toFixed(2)}</strong> this game ({g.saves}/{g.shots_against} saves)</div>
          </Tooltip>
        )}
      </div>
      <p className="axis-note">Game number · above 0 beats a league-average goalie</p>
    </figure>
  )
}

const ROLL = 5 // games in the rolling Corsi line

/**
 * 5v5 Corsi % (shot attempts for / all attempts while on the ice) for each game, as bars rising
 * or falling from the 50% line, plus a rolling line. Games the NHL has no shift data for are
 * left blank. `games` is chronological, each with an `onice` object or null.
 */
export function CorsiChart({ games }) {
  const [plotRef, W] = useWidth()
  const PW = W - M.l - M.r
  const n = games.length
  const pct = games.map((g) => (g.onice && g.onice.cf + g.onice.ca > 0 ? (100 * g.onice.cf) / (g.onice.cf + g.onice.ca) : null))

  // Rolling share over the last ROLL games that have data (not the last ROLL calendar games).
  const rolling = games.map((_, i) => {
    let cf = 0, ca = 0, seen = 0
    for (let j = i; j >= 0 && seen < ROLL; j--) {
      if (!games[j].onice) continue
      cf += games[j].onice.cf
      ca += games[j].onice.ca
      seen++
    }
    return games[i].onice && cf + ca > 0 ? (100 * cf) / (cf + ca) : null
  })

  const vals = pct.filter((v) => v != null)
  const lo = Math.floor(Math.min(40, ...vals) / 10) * 10
  const hi = Math.ceil(Math.max(60, ...vals) / 10) * 10
  const ticks = []
  for (let v = lo; v <= hi; v += 10) ticks.push(v)

  const slot = PW / Math.max(n, 8)
  const barW = Math.min(slot - 2, 28)
  const x = (i) => M.l + slot * i + slot / 2
  const y = (v) => M.t + PH - ((v - lo) / (hi - lo)) * PH
  const [idx, cursor] = useGameCursor(n, x, W)
  const step = Math.ceil(n / 10)
  const g = idx == null ? null : games[idx]

  const rollPath = rolling
    .map((v, i) => (v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`))
    .filter(Boolean)
    .map((pt, i) => `${i ? 'L' : 'M'}${pt}`)
    .join(' ')

  if (!vals.length) {
    return (
      <figure className="chart wide">
        <figcaption><h3>Corsi % by game (5v5)</h3></figcaption>
        <p className="status">The NHL hasn't published shift data for any of this player's games yet.</p>
      </figure>
    )
  }

  return (
    <figure className="chart wide">
      <figcaption>
        <h3>Corsi % by game (5v5)</h3>
        <ul className="legend">
          <li><i className="key box above" /> Above 50%</li>
          <li><i className="key box below" /> Below 50%</li>
          <li><i className="key solid roll" /> {ROLL}-game rolling</li>
        </ul>
      </figcaption>
      <div className="plot" ref={plotRef}>
        <svg
          width={W}
          height={H}
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label="5v5 Corsi percentage in each game with a rolling average"
          {...cursor}
        >
          {ticks.map((v) => (
            <g key={v}>
              <line x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} className={v === 50 ? 'zero-line' : 'grid'} />
              <text x={M.l - 8} y={y(v)} dy="0.32em" textAnchor="end" className="axis">{v}</text>
            </g>
          ))}
          {games.map((game, i) => (
            <g key={game.game_id}>
              {i === idx && <rect x={x(i) - slot / 2} y={M.t} width={slot} height={PH} className="hover-band" />}
              {pct[i] != null ? (
                <rect
                  x={x(i) - barW / 2}
                  y={Math.min(y(pct[i]), y(50))}
                  width={barW}
                  height={Math.max(Math.abs(y(pct[i]) - y(50)), 1)}
                  rx="3"
                  className={pct[i] >= 50 ? 'bar-above' : 'bar-below'}
                  opacity="0.85"
                />
              ) : (
                <line x1={x(i) - 6} x2={x(i) + 6} y1={y(50)} y2={y(50)} className="no-data" />
              )}
              {i % step === 0 && <text x={x(i)} y={H - 8} textAnchor="middle" className="axis">{i + 1}</text>}
            </g>
          ))}
          <path d={rollPath} className="roll-line" />
        </svg>
        {g && (
          <Tooltip W={W} x={x(idx)}>
            <div className="tip-head">Game {idx + 1} · {fmtDate(g.game_date)} {g.is_home ? 'vs' : '@'} {g.opponent}</div>
            {g.onice ? (
              <>
                <div className="tip-row"><strong>{pct[idx].toFixed(1)}%</strong> Corsi ({g.onice.cf} for, {g.onice.ca} against)</div>
                <div className="tip-row"><strong>{rolling[idx].toFixed(1)}%</strong> {ROLL}-game rolling</div>
                <div className="tip-head tip-sub">
                  Fenwick {g.onice.ff}–{g.onice.fa} · 5v5 goals {g.onice.gf}–{g.onice.ga}
                </div>
              </>
            ) : (
              <div className="tip-row">No shift data published for this game</div>
            )}
          </Tooltip>
        )}
      </div>
      <p className="axis-note">Game number · games without NHL shift data show a short gray tick on the 50% line</p>
    </figure>
  )
}

/**
 * Overlaid lines for comparing players on a shared integer x axis (career year or age).
 * series: [{ id, name, slot (1-3), points: [{ x, y }] }]. Names are direct-labelled at line ends.
 */
export function CompareChart({ title, series, xLabel, yLabel, yDomain, yFmt = (v) => v }) {
  const [plotRef, W] = useWidth()
  const R = 92 // room for end-of-line labels
  const PW = W - M.l - R
  const all = series.flatMap((s) => s.points)
  const xMin = Math.min(...all.map((p) => p.x))
  const xMax = Math.max(...all.map((p) => p.x))
  const span = Math.max(xMax - xMin, 1)
  // Zero-based integer axis by default; callers can pass { min, max, ticks } for rates like save %.
  const axis = yDomain ?? { min: 0, ...niceAxis(Math.max(...all.map((p) => p.y), 1), 1), max: undefined }
  const lo = axis.min
  const hi = yDomain ? axis.max : axis.top
  const ticks = axis.ticks
  const x = (v) => M.l + ((v - xMin) / span) * PW
  const y = (v) => M.t + PH - ((v - lo) / (hi - lo)) * PH
  const xs = Array.from({ length: xMax - xMin + 1 }, (_, i) => xMin + i)
  const [idx, cursor] = useGameCursor(xs.length, (i) => x(xs[i]), W)
  const at = idx == null ? null : xs[idx]
  const step = Math.ceil(xs.length / 12)

  // End labels, nudged apart so close finishes don't overprint.
  const ends = series
    .map((s) => ({ s, p: s.points[s.points.length - 1] }))
    .filter((e) => e.p)
    .sort((a, b) => y(a.p.y) - y(b.p.y))
  let lastY = -Infinity
  for (const e of ends) {
    e.ly = Math.max(y(e.p.y), lastY + 13)
    lastY = e.ly
  }

  return (
    <figure className="chart wide">
      <figcaption>
        <h3>{title}</h3>
        <ul className="legend">
          {series.map((s) => (
            <li key={s.id}><i className={`key solid cmp-key-${s.slot}`} /> {s.name}</li>
          ))}
        </ul>
      </figcaption>
      <div className="plot" ref={plotRef}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title} {...cursor}>
          {ticks.map((v) => (
            <g key={v}>
              <line x1={M.l} x2={W - R} y1={y(v)} y2={y(v)} className="grid" />
              <text x={M.l - 8} y={y(v)} dy="0.32em" textAnchor="end" className="axis">{yFmt(v)}</text>
            </g>
          ))}
          {xs.map((v, i) =>
            i % step === 0 ? (
              <text key={v} x={x(v)} y={H - 8} textAnchor="middle" className="axis">{v}</text>
            ) : null,
          )}
          {series.map((s) => (
            <g key={s.id}>
              <path
                d={s.points.map((p, i) => `${i ? 'L' : 'M'}${x(p.x).toFixed(1)},${y(p.y).toFixed(1)}`).join(' ')}
                className={`cmp-line cmp-${s.slot}`}
              />
              {s.points.map((p) => (
                <circle key={p.x} cx={x(p.x)} cy={y(p.y)} r={p.x === at ? 4.5 : 2.5} className={`cmp-dot cmp-fill-${s.slot}`} />
              ))}
            </g>
          ))}
          {ends.map((e) => (
            <text key={e.s.id} x={x(e.p.x) + 8} y={e.ly} dy="0.32em" className="end-label">{e.s.name}</text>
          ))}
          {at != null && <line x1={x(at)} x2={x(at)} y1={M.t} y2={M.t + PH} className="cross" pointerEvents="none" />}
        </svg>
        {at != null && (
          <Tooltip W={W} x={x(at)}>
            <div className="tip-head">{xLabel} {at}</div>
            {series.map((s) => {
              const p = s.points.find((q) => q.x === at)
              return (
                <div className="tip-row" key={s.id}>
                  <i className={`key solid cmp-key-${s.slot}`} />
                  <strong>{p ? yFmt(p.y) : '–'}</strong> {s.name}
                </div>
              )
            })}
          </Tooltip>
        )}
      </div>
      <p className="axis-note">{xLabel} · {yLabel}</p>
    </figure>
  )
}

/**
 * A trend line over a season's games: each game's own value as a dot, a rolling line over the last `w` games, and
 * dashed reference lines for the season average and (optionally) a league figure. `games` is chronological and
 * `raw` / `roll` have one entry per game (null where there is nothing to draw). `tip(i)` returns the tooltip rows.
 */
export function RollingChart({ title, games, raw, roll, avg, avgLabel, refLine, w, rawLabel, fmt, domain, ticks, tip, note }) {
  const [plotRef, W] = useWidth()
  const PW = W - M.l - M.r
  const n = games.length
  const nums = [...raw, ...roll, avg, refLine?.value].filter((v) => v != null)
  const auto = niceAxis(Math.max(...nums, 0))
  const [lo, hi] = domain ?? [0, auto.top]
  const tickList = ticks ?? auto.ticks
  const slot = PW / Math.max(n, 8)
  const x = (i) => M.l + slot * i + slot / 2
  const y = (v) => M.t + PH - ((Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo)) * PH
  const [idx, cursor] = useGameCursor(n, x, W)
  const step = Math.ceil(n / 10)
  const g = idx == null ? null : games[idx]
  const rollPath = roll
    .map((v, i) => (v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`))
    .filter(Boolean)
    .map((pt, i) => `${i ? 'L' : 'M'}${pt}`)
    .join(' ')

  return (
    <figure className="chart wide">
      <figcaption>
        <h3>{title}</h3>
        <ul className="legend">
          <li><i className="key box above" /> {rawLabel}</li>
          <li><i className="key solid roll" /> {w}-game rolling</li>
          <li><i className="key dashed" /> {avgLabel}</li>
          {refLine && <li><i className="key dashed" style={{ borderTopColor: 'var(--series-2)' }} /> {refLine.label}</li>}
        </ul>
      </figcaption>
      <div className="plot" ref={plotRef}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}: each game and a ${w}-game rolling line`} {...cursor}>
          {tickList.map((v) => (
            <g key={v}>
              <line x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} className="grid" />
              <text x={M.l - 8} y={y(v)} dy="0.32em" textAnchor="end" className="axis">{fmt(v)}</text>
            </g>
          ))}
          {avg != null && <line x1={M.l} x2={W - M.r} y1={y(avg)} y2={y(avg)} stroke="var(--muted)" strokeWidth="1.5" strokeDasharray="5 4" />}
          {refLine && <line x1={M.l} x2={W - M.r} y1={y(refLine.value)} y2={y(refLine.value)} stroke="var(--series-2)" strokeWidth="1.5" strokeDasharray="5 4" />}
          {games.map((game, i) => (
            <g key={game.game_id}>
              {i === idx && <rect x={x(i) - slot / 2} y={M.t} width={slot} height={PH} className="hover-band" />}
              {raw[i] != null && <circle cx={x(i)} cy={y(raw[i])} r="3.5" fill="var(--series-1)" opacity="0.5" />}
              {i % step === 0 && <text x={x(i)} y={H - 8} textAnchor="middle" className="axis">{i + 1}</text>}
            </g>
          ))}
          <path d={rollPath} className="roll-line" />
        </svg>
        {g && (
          <Tooltip W={W} x={x(idx)}>
            <div className="tip-head">Game {idx + 1} · {fmtDate(g.game_date)} {g.is_home ? 'vs' : '@'} {g.opponent}</div>
            {tip(idx)}
          </Tooltip>
        )}
      </div>
      <p className="axis-note">Game number{note ? ` · ${note}` : ''}</p>
    </figure>
  )
}
