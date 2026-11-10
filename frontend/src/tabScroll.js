// Tab rows that scroll sideways on a phone (.tabs, .subtabs): a soft fade on the edge where more tabs are hidden, so a cut-off tab
// reads as "there is more" and not as a mistake, and the open tab is scrolled into view (a link can open straight to a later tab).
// The row gets data-scroll = none | start | middle | end, which index.css turns into the fades. The decisions are the two pure
// functions below; installTabScroll finds the rows, including ones that appear later as pages change.

/** Where a scrolling row is: 'none' (everything fits), 'start' (more to the right), 'middle' (more both sides) or 'end' (more to the left). */
export function scrollState(scrollLeft, clientWidth, scrollWidth) {
  const max = scrollWidth - clientWidth
  if (max <= 1) return 'none'
  if (scrollLeft <= 1) return 'start'
  if (scrollLeft >= max - 1) return 'end'
  return 'middle'
}

/**
 * The scrollLeft that puts an item fully in view (centered where there is room), or null when it already is.
 * itemLeft is the item's left edge within the row's scrollable content.
 */
export function revealLeft({ viewWidth, scrollWidth, scrollLeft, itemLeft, itemWidth }) {
  if (itemLeft >= scrollLeft && itemLeft + itemWidth <= scrollLeft + viewWidth) return null
  const centered = itemLeft - (viewWidth - itemWidth) / 2
  return Math.max(0, Math.min(centered, Math.max(0, scrollWidth - viewWidth)))
}

const ROWS = '.tabs, .subtabs'
const OPEN = '.on, [aria-selected="true"]'

function refresh(row) {
  row.dataset.scroll = scrollState(row.scrollLeft, row.clientWidth, row.scrollWidth)
}

function reveal(row, smooth) {
  const open = row.querySelector(OPEN)
  if (!open || row.scrollWidth <= row.clientWidth + 1) return
  const left = open.getBoundingClientRect().left - row.getBoundingClientRect().left + row.scrollLeft
  const target = revealLeft({ viewWidth: row.clientWidth, scrollWidth: row.scrollWidth, scrollLeft: row.scrollLeft, itemLeft: left, itemWidth: open.offsetWidth })
  if (target != null) row.scrollTo({ left: target, behavior: smooth ? 'smooth' : 'auto' }) // scrolls only this row, never the page
}

/** Start watching `root` for tab rows. Returns a function that stops. */
export function installTabScroll(root = document) {
  const bound = new WeakSet()
  const sizes = typeof ResizeObserver === 'function' ? new ResizeObserver((entries) => entries.forEach((e) => refresh(e.target))) : null
  const bind = (row) => {
    if (bound.has(row)) return
    bound.add(row)
    row.addEventListener('scroll', () => refresh(row), { passive: true })
    sizes?.observe(row)
    refresh(row)
    reveal(row, false)
    refresh(row)
  }
  const scan = (node) => {
    if (node.nodeType !== 1) return
    if (node.matches(ROWS)) bind(node)
    node.querySelectorAll?.(ROWS).forEach(bind)
  }
  let pending = new Set()
  let frame = 0
  const flush = () => {
    frame = 0
    pending.forEach((row) => { refresh(row); reveal(row, true); refresh(row) })
    pending = new Set()
  }
  const watcher = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.type === 'childList') {
        m.addedNodes.forEach(scan)
        const row = m.target.nodeType === 1 ? m.target.closest?.(ROWS) : null   // tabs added or removed inside a row
        if (row) pending.add(row)
      } else {
        const row = m.target.closest?.(ROWS)   // a tab was opened or closed
        if (row) pending.add(row)
      }
    }
    if (pending.size && !frame) frame = requestAnimationFrame(flush)
  })
  scan(root.body ?? root)
  watcher.observe(root.body ?? root, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'aria-selected'] })
  return () => {
    watcher.disconnect()
    sizes?.disconnect()
    if (frame) cancelAnimationFrame(frame)
  }
}
