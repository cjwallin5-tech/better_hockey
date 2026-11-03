import { teamColor } from '../teamColors.js'

/**
 * The two teams side by side, one row per measure: each number at its end and a bar split in proportion, in team colours. rows:
 * [[label, awayValue, homeValue, shown]]. Values are numbers (zero on both sides draws an even grey bar).
 */
export default function GameVersus({ away, home, rows }) {
  const colors = { a: teamColor(away), h: teamColor(home) }
  return (
    <div className="versus">
      <div className="vs-sides"><strong>{away}</strong><strong>{home}</strong></div>
      {rows.map(([label, a, h, fmt = (v) => v]) => {
        const total = a + h
        const share = total > 0 ? (100 * a) / total : 50
        return (
          <div key={label} className="vs-row">
            <div className="vs-head"><strong>{fmt(a)}</strong><span>{label}</span><strong>{fmt(h)}</strong></div>
            <div className="vs-bar" role="img" aria-label={`${label}: ${away} ${fmt(a)}, ${home} ${fmt(h)}`}>
              <i style={{ width: `${share}%`, background: total > 0 ? colors.a : 'var(--line)' }} />
              <i style={{ flex: 1, background: total > 0 ? colors.h : 'var(--line)' }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}
