import Info from './Info.jsx'
import Note from './Note.jsx'

/**
 * A page's title with its introduction behind an Info icon. Pages that also appear inside another page (`embedded`) have no title of their
 * own, so the same text shows as a one-line note instead and is not lost.
 */
export default function PageIntro({ title, embedded = false, children }) {
  if (embedded) return children ? <Note label="About this page">{children}</Note> : null
  return <h1>{title}{children && <Info label={title}>{children}</Info>}</h1>
}
