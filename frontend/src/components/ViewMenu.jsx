/**
 * One dropdown that replaces a row of stat tabs: every view on the page in a single menu, grouped under headings.
 * groups: [{ label, views: [{ id, label }] }]; activeId: the open view; onSelect(id). A group with no label is listed bare.
 */
export default function ViewMenu({ groups, activeId, onSelect, label = 'Show' }) {
  return (
    <div className="controls view-menu">
      <label>
        {label}
        <select value={activeId} onChange={(e) => onSelect(e.target.value)} aria-label={label}>
          {groups.map((g) => g.label ? (
            <optgroup key={g.label} label={g.label}>
              {g.views.map((v) => <option key={v.id} value={v.id}>{v.label}</option>)}
            </optgroup>
          ) : g.views.map((v) => <option key={v.id} value={v.id}>{v.label}</option>))}
        </select>
      </label>
    </div>
  )
}
