import { useState } from 'react'

/**
 * The control row above a table: the few filters people use all the time stay in the row (`main`), and the rest sit behind one
 * "Filters" button (`extra`) that shows how many of them are set. `tail` is for the row's end (download, count). The panel starts open
 * when a link arrives with filters already set, so nothing is silently hiding. Without `extra` there is no button.
 * count: how many of the `extra` filters are set; onClear resets them.
 */
export default function FilterPanel({ main, extra, tail, count = 0, onClear }) {
  const [open, setOpen] = useState(count > 0)
  return (
    <>
      <div className="controls">
        {main}
        {extra && (
          <button type="button" className={`filters-toggle${open ? ' open' : ''}`} aria-expanded={open} onClick={() => setOpen(!open)}>
            Filters{count > 0 && <b className="filters-count">{count}</b>} <span aria-hidden="true">{open ? '▴' : '▾'}</span>
          </button>
        )}
        {tail}
      </div>
      {extra && open && (
        <div className="controls filter-panel">
          {extra}
          {count > 0 && onClear && <button type="button" className="link-button" onClick={onClear}>Clear filters</button>}
        </div>
      )}
    </>
  )
}
