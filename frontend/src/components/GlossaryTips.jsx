import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { describe } from '../glossary.js'
import { baseLabel, glossaryLink } from '../glossaryPage.js'

const WIDTH = 320
const HIDE_MS = 160

/**
 * Hovering a stat label in any table header shows what it means and a link to its full entry in the glossary. It replaces the browser's
 * own tooltip for those headers (which cannot hold a link) and listens at the page level, so every table gets it without changes.
 * The popover stays open while the pointer is over it, so the link can be clicked.
 */
export default function GlossaryTips() {
  const [tip, setTip] = useState(null) // { label, text, top, left }
  const timer = useRef(null)
  const holder = useRef(null) // the header whose native title is set aside while the popover shows

  useEffect(() => {
    const restore = () => {
      const el = holder.current
      if (el?.dataset.title !== undefined) { el.title = el.dataset.title; delete el.dataset.title }
      holder.current = null
    }
    const hide = () => { clearTimeout(timer.current); timer.current = setTimeout(() => { setTip(null); restore() }, HIDE_MS) }
    const over = (e) => {
      const th = e.target instanceof Element ? e.target.closest('th') : null
      if (!th) return
      const label = th.textContent.replace(/[▲▼]/g, '').trim()
      const text = label && describe(label)
      if (!text) return
      clearTimeout(timer.current)
      if (holder.current !== th) {
        restore()
        if (th.title) { th.dataset.title = th.title; th.removeAttribute('title') }
        holder.current = th
      }
      const r = th.getBoundingClientRect()
      setTip({ label, text, top: r.bottom + 6, left: Math.max(8, Math.min(r.left, window.innerWidth - WIDTH - 8)) })
    }
    const out = (e) => { if (e.target instanceof Element && e.target.closest('th')) hide() }
    document.addEventListener('mouseover', over)
    document.addEventListener('mouseout', out)
    const away = () => { clearTimeout(timer.current); setTip(null); restore() }
    window.addEventListener('scroll', away, { passive: true })
    return () => {
      document.removeEventListener('mouseover', over); document.removeEventListener('mouseout', out); window.removeEventListener('scroll', away)
      clearTimeout(timer.current); restore()
    }
  }, [])

  if (!tip) return null
  return (
    <div
      className="term-pop" role="tooltip" style={{ top: tip.top, left: tip.left, width: WIDTH }}
      onMouseEnter={() => clearTimeout(timer.current)}
      onMouseLeave={() => { timer.current = setTimeout(() => setTip(null), HIDE_MS) }}
    >
      <strong>{baseLabel(tip.label)}</strong>
      <p>{tip.text}</p>
      <Link to={glossaryLink(tip.label)} onClick={() => setTip(null)}>Full definition in the glossary &rarr;</Link>
    </div>
  )
}
