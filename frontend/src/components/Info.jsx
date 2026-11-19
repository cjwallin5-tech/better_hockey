import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from './Icon.jsx'
import { infoPosition } from '../infoPosition.js'

const WIDTH = 320

/**
 * A small "i" beside a heading or value: tap, click or press Enter to read a short explanation, instead of putting the explanation on
 * the page. Keep the text to a sentence or two. The popover is drawn at the
 * top of the page, so a card's clipped edges can't cut it off, and closes on Escape, a click elsewhere or scrolling.
 */
export default function Info({ label, children }) {
  const [pos, setPos] = useState(null)
  const button = useRef(null)
  const id = useId()

  const close = () => setPos(null)
  const toggle = () => {
    if (pos) return close()
    setPos(infoPosition(button.current.getBoundingClientRect(), { width: window.innerWidth, height: window.innerHeight }, WIDTH))
  }

  useEffect(() => {
    if (!pos) return undefined
    const onKey = (e) => { if (e.key === 'Escape') { close(); button.current?.focus() } }
    const onDown = (e) => { if (!button.current?.contains(e.target) && !e.target.closest?.('.info-pop')) close() }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onDown)
    window.addEventListener('scroll', close, { passive: true })
    window.addEventListener('resize', close)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onDown)
      window.removeEventListener('scroll', close)
      window.removeEventListener('resize', close)
    }
  }, [pos])

  return (
    <>
      <button ref={button} type="button" className="info" aria-label={`About ${label}`} aria-expanded={Boolean(pos)} aria-controls={pos ? id : undefined} onClick={toggle}>
        <Icon name="info" size="1em" />
      </button>
      {pos && createPortal(
        <div id={id} role="dialog" aria-label={label} className="term-pop info-pop" style={{ ...pos, width: WIDTH }}>
          <strong>{label}</strong>
          <p>{children}</p>
        </div>,
        document.body,
      )}
    </>
  )
}
