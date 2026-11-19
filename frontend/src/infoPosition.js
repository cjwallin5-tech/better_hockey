// Where an Info popover goes: under its button when there is room, above it when the button is near the bottom of the screen, and
// kept inside the screen sideways. Returns the fixed-position style ({ top } or { bottom }, and left).

/** rect: the button's bounding box; viewport: { width, height }. */
export function infoPosition(rect, viewport, width = 320, gap = 6, minRoom = 220) {
  const left = Math.max(8, Math.min(rect.left - 8, viewport.width - width - 8))
  const below = viewport.height - rect.bottom
  return below >= minRoom || below >= rect.top
    ? { top: rect.bottom + gap, left }
    : { bottom: viewport.height - rect.top + gap, left }
}
