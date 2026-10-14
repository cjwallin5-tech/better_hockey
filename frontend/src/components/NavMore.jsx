import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'

/** A "More" dropdown for the less-used pages so the top bar stays short. items: [[path, label]] */
export default function NavMore({ items }) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const ref = useRef(null)
  const { pathname } = useLocation()
  const here = items.some(([to]) => pathname.startsWith(to))

  useEffect(() => {
    if (!open) return
    const away = (e) => !ref.current?.contains(e.target) && setOpen(false)
    const esc = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', away)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', away); document.removeEventListener('keydown', esc) }
  }, [open])

  return (
    <div className="nav-more" ref={ref}>
      <button className={`nav-more-btn ${here ? 'active' : ''}`} aria-expanded={open} aria-haspopup="true" onClick={(e) => {
          // Fixed positioning so the menu isn't clipped by the scrollable nav bar.
          const r = e.currentTarget.getBoundingClientRect()
          setPos({ top: r.bottom + 4, left: Math.max(8, Math.min(r.left, window.innerWidth - 168)) })
          setOpen(!open)
        }}>
        More ▾
      </button>
      {open && (
        <div className="nav-more-menu" style={pos} onClick={() => setOpen(false)}>
          {items.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}
        </div>
      )}
    </div>
  )
}
