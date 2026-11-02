/** Angle of spoke i of n, in radians, with spoke 0 pointing straight up and the rest running clockwise. */
export const spokeAngle = (i, n) => (Math.PI * 2 * i) / n - Math.PI / 2

/** The point at `pct` (0-100) of the radius along spoke i of n, around (cx, cy). */
export function radarPoint(i, n, pct, cx, cy, r) {
  const a = spokeAngle(i, n)
  const d = (r * Math.max(0, Math.min(100, pct ?? 0))) / 100
  return { x: cx + d * Math.cos(a), y: cy + d * Math.sin(a) }
}

/** SVG polygon points for a list of percentiles (null counts as 0, the centre). */
export function radarPolygon(values, cx, cy, r) {
  return values
    .map((v, i) => radarPoint(i, values.length, v, cx, cy, r))
    .map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(' ')
}

/** "91st", "62nd", "13th": a percentile as a rank-style word. */
export function ordinal(n) {
  if (n == null) return '–'
  const v = n % 100
  if (v >= 11 && v <= 13) return `${n}th`
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'}`
}

/** Display text for an axis value: ice time as m:ss, rates to one or two decimals, shares as a percentage. */
export function axisValue(a) {
  if (a.value == null) return '–'
  if (a.key === 'icetime') return `${Math.floor(a.value / 60)}:${String(Math.round(a.value % 60)).padStart(2, '0')}`
  if (a.key === 'possession') return `${(a.value * 100).toFixed(1)}%`
  if (a.key === 'speed') return a.value.toFixed(1)
  return a.value.toFixed(2)
}
