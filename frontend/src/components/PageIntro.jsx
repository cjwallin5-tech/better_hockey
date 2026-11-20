import Note from './Note.jsx'

/**
 * A page's title with one short line under it saying what the page is. Anything longer (where the numbers come from, how a figure is
 * worked out) goes in `children` and shows as a small "More detail" note with an Info icon; leave it out when the subtitle says enough.
 * Pages that also appear inside another page (`embedded`) have no title of their own, but keep the subtitle and the note.
 */
export default function PageIntro({ title, subtitle, embedded = false, children }) {
  return (
    <>
      {!embedded && <h1>{title}</h1>}
      {subtitle && <p>{subtitle}</p>}
      {children && <Note label="More detail">{children}</Note>}
    </>
  )
}
