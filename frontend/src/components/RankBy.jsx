/**
 * "Rank by" dropdown for a leaderboard: the stats people sort by most in one menu, so changing what the list is ranked on does not mean
 * hunting for a column header, plus a button that flips the order. options: [{ key, label }]; sort: { key, dir }; onPick(key) picks a stat,
 * and picking the stat already in use flips the direction (the pages' sort handlers work that way), which is what the button does.
 */
export default function RankBy({ options, sort, onPick }) {
  if (options.length === 0) return null
  const inMenu = options.some((o) => o.key === sort.key)
  const desc = sort.dir !== 'asc'
  return (
    <div className="controls rankby">
      <label>
        Rank by
        <select value={inMenu ? sort.key : ''} onChange={(e) => onPick(e.target.value)} aria-label="Rank by">
          {!inMenu && <option value="" disabled>Sorted by a column heading</option>}
          {options.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
        </select>
      </label>
      <button
        type="button" className="rankby-dir" onClick={() => onPick(sort.key)}
        title="Flip the order" aria-label={desc ? 'Highest first; click to show lowest first' : 'Lowest first; click to show highest first'}
      >
        <i aria-hidden="true">{desc ? '▼' : '▲'}</i> {desc ? 'High to low' : 'Low to high'}
      </button>
    </div>
  )
}
