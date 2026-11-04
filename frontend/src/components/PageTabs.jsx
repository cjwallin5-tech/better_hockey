import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

const HOLD_MS = 1500

/**
 * Splits a long page into tabs so only one section is on screen (and mounted, so its data loads on demand).
 * The open tab lives in ?tab= so links, reloads and the back button keep the place.
 * tabs: [{ id, label, content, group? }]; the first tab is the default. `param` is the query key (a page with tabs inside a tab
 * gives the inner ones their own), and `pills` draws the tabs as small pills for an inner level. When tabs have a group, the groups show as the
 * main row and the open group's tabs as a second row, so a long list of tabs does not wrap into a wall of buttons.
 * `resetOnSwitch` clears every other query parameter when the tab changes (for pages whose tabs are whole pages with their own filters).
 */
export default function PageTabs({ tabs, param = 'tab', pills = false, resetOnSwitch = false }) {
  const [params, setParams] = useSearchParams()
  // Switching tabs unmounts the old content before the new content has loaded, which can shrink the page below the scroll
  // position and throw you to the top. Hold the panel at its old height while the new tab fills in.
  const panel = useRef(null)
  const [hold, setHold] = useState(null)
  useEffect(() => {
    if (hold == null) return undefined
    const t = setTimeout(() => setHold(null), HOLD_MS)
    return () => clearTimeout(t)
  }, [hold])
  const active = tabs.find((t) => t.id === params.get(param)) ?? tabs[0]
  const select = (id) => {
    setHold(panel.current?.offsetHeight ?? null)
    // resetOnSwitch: each tab keeps its own filters in the URL, so leaving a tab drops them (they would mean something else on another tab).
    const next = resetOnSwitch ? new URLSearchParams() : new URLSearchParams(params)
    if (id === tabs[0].id) next.delete(param)
    else next.set(param, id)
    setParams(next, { replace: true })
  }
  const tabButton = (t) => (
    <button key={t.id} role="tab" aria-selected={t.id === active.id} className={t.id === active.id ? 'on' : ''} onClick={() => select(t.id)}>
      {t.label}
    </button>
  )

  const groups = [...new Set(tabs.map((t) => t.group).filter(Boolean))]
  if (groups.length === 0) {
    return (
      <>
        <div className={pills ? 'subtabs' : 'tabs page-tabs'} role="tablist">{tabs.map(tabButton)}</div>
        <div role="tabpanel" ref={panel} style={hold ? { minHeight: hold } : undefined}>{active.content}</div>
      </>
    )
  }
  const inGroup = tabs.filter((t) => t.group === active.group)
  return (
    <>
      <div className="tabs page-tabs" role="tablist">
        {groups.map((g) => {
          const first = tabs.find((t) => t.group === g)
          return (
            <button key={g} role="tab" aria-selected={g === active.group} className={g === active.group ? 'on' : ''} onClick={() => g !== active.group && select(first.id)}>
              {g}
            </button>
          )
        })}
      </div>
      {inGroup.length > 1 && <div className="subtabs" role="tablist">{inGroup.map(tabButton)}</div>}
      <div role="tabpanel" ref={panel} style={hold ? { minHeight: hold } : undefined}>{active.content}</div>
    </>
  )
}
