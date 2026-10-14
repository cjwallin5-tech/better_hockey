import { useSearchParams } from 'react-router-dom'

/**
 * Splits a long page into tabs so only one section is on screen (and mounted, so its data loads on demand).
 * The open tab lives in ?tab= so links, reloads and the back button keep the place.
 * tabs: [{ id, label, content }]; the first tab is the default.
 */
export default function PageTabs({ tabs }) {
  const [params, setParams] = useSearchParams()
  const active = tabs.find((t) => t.id === params.get('tab')) ?? tabs[0]
  const select = (id) => {
    const next = new URLSearchParams(params)
    if (id === tabs[0].id) next.delete('tab')
    else next.set('tab', id)
    setParams(next, { replace: true })
  }
  return (
    <>
      <div className="tabs page-tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t.id} role="tab" aria-selected={t.id === active.id} className={t.id === active.id ? 'on' : ''} onClick={() => select(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">{active.content}</div>
    </>
  )
}
