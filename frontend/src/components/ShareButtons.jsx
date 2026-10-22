import { useState } from 'react'
import { drawCard, downloadCanvas } from '../shareCard.js'

/**
 * "Copy link" copies the current page address (the pages keep their picks in the URL); "Save image" downloads a PNG
 * card of `card` (see drawCard in shareCard.js). Leave `card` out to show only the link button.
 */
export default function ShareButtons({ card, filename = 'nhl-stats.png', link }) {
  const [msg, setMsg] = useState('')

  const copy = async () => {
    const url = link ?? window.location.href
    try {
      await navigator.clipboard.writeText(url)
      setMsg('Link copied.')
    } catch {
      setMsg(url) // clipboard blocked: show it so it can be copied by hand
    }
  }
  const save = () => {
    downloadCanvas(drawCard(card), filename)
    setMsg('Image saved.')
  }

  return (
    <div className="roster-tools">
      <button onClick={copy}>Copy link</button>
      {card && <button onClick={save}>Save image</button>}
      {msg && <span className="muted" role="status"> {msg}</span>}
    </div>
  )
}
