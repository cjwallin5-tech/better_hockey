/**
 * "Rank by" quick picks for a leaderboard: one button per stat people sort by most, so changing what the list is ranked on is one click
 * instead of hunting for a column header. options: [{ key, label }]; the active one shows the direction, and clicking it again flips it.
 */
export default function RankBy({ options, sort, onPick }) {
  if (options.length === 0) return null
  return (
    <div className="rankby" role="group" aria-label="Rank by">
      <span className="rankby-label">Rank by</span>
      {options.map((o) => {
        const on = sort.key === o.key
        return (
          <button
            key={o.key} type="button" className={`rankby-chip${on ? ' on' : ''}`} aria-pressed={on}
            title={on ? 'Click again to flip the order' : `Rank by ${o.label}`} onClick={() => onPick(o.key)}
          >
            {o.label}{on && <i aria-hidden="true">{sort.dir === 'asc' ? ' ▲' : ' ▼'}</i>}
          </button>
        )
      })}
    </div>
  )
}
