// Zone geometry for the goalie weakness map. Rink coordinates are feet with the attacked net at (89, 0); a shot's
// range is its distance from the net and its lane the angle off straight-on (matching backend/goaliemap.py).
export const NET_X = 89
export const RANGE_FT = { close: [0, 15], mid: [15, 35], long: [35, 62] }
export const MIDDLE_ANGLE = 15
export const RANGE_LABEL = { close: 'Close (under 15 ft)', mid: 'Mid (15-35 ft)', long: 'Long (35 ft +)' }
export const LANE_LABEL = { glove: 'Glove side', middle: 'Middle', blocker: 'Blocker side' }

/** Rink y sign of the glove side: a left-catching goalie has the glove toward negative y (the shooter's left is +y). */
export const gloveSign = (catches) => (catches === 'R' ? 1 : -1)

/** The point at `dist` feet from the net and `deg` degrees off straight-on toward the side `sign` (+1 or -1). */
export function polar(dist, deg, sign) {
  const a = (deg * Math.PI) / 180
  return { x: NET_X - dist * Math.cos(a), y: sign * dist * Math.sin(a) }
}

/**
 * Outline of a zone as rink points. The middle lane spans -15 to +15 degrees; a side lane runs from 15 to 90
 * degrees on its side. `sign` is the side (+1/-1) for a side lane and ignored for the middle.
 */
export function zonePolygon(range, lane, sign, steps = 10) {
  const [r0, r1] = RANGE_FT[range]
  const [a0, a1] = lane === 'middle' ? [-MIDDLE_ANGLE, MIDDLE_ANGLE] : [MIDDLE_ANGLE, 90]
  const at = (d, i) => {
    const a = a0 + ((a1 - a0) * i) / steps
    return lane === 'middle' ? polar(d, Math.abs(a), a < 0 ? -1 : 1) : polar(d, a, sign)
  }
  const idx = Array.from({ length: steps + 1 }, (_, i) => i)
  const outer = idx.map((i) => at(r1, i))
  const inner = r0 === 0 ? [{ x: NET_X, y: 0 }] : idx.map((i) => at(r0, i)).reverse()
  return [...outer, ...inner]
}

/** Where to put a zone's label: halfway through its range, in the middle of its lane. */
export function zoneCentre(range, lane, sign) {
  const [r0, r1] = RANGE_FT[range]
  const d = (r0 + r1) / 2
  return lane === 'middle' ? polar(d, 0, 1) : polar(d, 52, sign)
}

/** Fill opacity for a graded zone: 0 at the average, full at |z| >= 2. */
export const zoneStrength = (z) => Math.min(1, Math.abs(z ?? 0) / 2)

export const signed = (v, d = 1) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(d)}`)
