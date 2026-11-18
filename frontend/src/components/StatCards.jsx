/** "1st", "2nd", "13th". */
export const ordinal = (n) => {
  const v = n % 100
  if (v >= 11 && v <= 13) return `${n}th`
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'}`
}

/**
 * A grid of stat cards, each with the value, a bar for its percentile among peers and a footnote. stats: [{ key, label, fmt?, note? }];
 * p holds the values by key and percentiles the 0-100 percentile by key (missing means no data). Shared by the skater and goalie pages.
 */
export function StatCards({ stats, p, percentiles }) {
  return (
    <div className="def-grid">
      {stats.map((d) => {
        const pct = percentiles[d.key]
        return (
          <div className="def-card" key={d.key}>
            <div className="def-top">
              <span>{d.label}</span>
              <strong>{p[d.key] == null ? '–' : d.fmt ? d.fmt(p[d.key]) : p[d.key]}</strong>
            </div>
            <div className="bar" title={pct == null ? '' : `${ordinal(pct)} percentile`}>
              <div className={pct == null ? '' : pct >= 75 ? 'lv-hi' : pct < 35 ? 'lv-lo' : ''} style={{ width: `${pct ?? 0}%` }} />
            </div>
            <div className="def-foot">
              {pct == null ? 'no data' : `${ordinal(pct)} percentile`}
              {d.note && <em> · {d.note}</em>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/** One number with a label and an optional rank caption underneath. */
export function Tile({ label, value, rank }) {
  return (
    <div className="tile">
      <span>{label}</span>
      <strong>{value ?? '–'}</strong>
      {rank && <small className="tile-rank">{rank}</small>}
    </div>
  )
}
