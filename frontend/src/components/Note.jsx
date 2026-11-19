import Info from './Info.jsx'

/**
 * A one-line stand-in for a footnote or caption: a short label with an Info icon that holds the explanation. Use it where text used to
 * trail a chart or table ("How to read the map") so the page shows the label, not the paragraph.
 */
export default function Note({ label, children }) {
  return (
    <p className="note-line">
      <span>{label}</span>
      <Info label={label}>{children}</Info>
    </p>
  )
}
