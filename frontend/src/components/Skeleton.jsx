// Gray placeholder shapes shown while a page's data loads. They fade in after a beat (see .sk-fade), so a fast load shows nothing at all.
const WIDTHS = [100, 92, 100, 84, 96, 100, 88, 94]

/** A few shimmering rows, for a section that is still loading inside a page. */
export function Skeleton({ rows = 5 }) {
  return (
    <div className="sk-fade sk-block" role="status" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => <div key={i} className="sk sk-row" style={{ width: `${WIDTHS[i % WIDTHS.length]}%` }} />)}
    </div>
  )
}

/** A whole page's worth: a title, a line of text, optional stat cards, then a table. Sits inside <main>. */
export default function PageSkeleton({ cards = false, rows = 9 }) {
  return (
    <div className="sk-fade" role="status" aria-busy="true" aria-label="Loading">
      <div className="sk sk-title" />
      <div className="sk sk-line" />
      {cards && (
        <div className="sk-cards">
          {[0, 1, 2, 3].map((i) => <div key={i} className="sk sk-card" />)}
        </div>
      )}
      <div className="sk-table">
        {Array.from({ length: rows }, (_, i) => <div key={i} className="sk sk-row" />)}
      </div>
    </div>
  )
}
