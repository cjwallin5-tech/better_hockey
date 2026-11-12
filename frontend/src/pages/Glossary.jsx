import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { GROUPS } from '../glossaryPage.js'
import { TERM_LIST } from '../glossary.js'

const matches = (text, q) => text.toLowerCase().includes(q)

/** What every stat on the site means, in plain language: grouped explanations, then every column label A to Z. Terms have #links. */
export default function Glossary() {
  const { hash } = useLocation()
  const [params] = useSearchParams()
  const [query, setQuery] = useState(() => params.get('q') ?? '') // a hover popover can link here with its label already searched
  const q = query.trim().toLowerCase()

  // A link like /glossary#corsi scrolls to its term once the page is drawn.
  useEffect(() => {
    if (!hash) return
    document.getElementById(hash.slice(1))?.scrollIntoView({ block: 'start' })
  }, [hash])

  const groups = useMemo(() => GROUPS.map((g) => ({
    ...g,
    terms: q ? g.terms.filter((t) => [t.name, t.abbr, t.what, t.read ?? ''].some((x) => matches(x, q))) : g.terms,
  })).filter((g) => g.terms.length > 0), [q])
  const list = useMemo(() => (q ? TERM_LIST.filter(([k, v]) => matches(k, q) || matches(v, q)) : TERM_LIST), [q])

  return (
    <main className="glossary">
      <header>
        <h1>Glossary</h1>
        <p>What every stat on Faceoff means, in plain language. Click a column label anywhere on the site to see its short meaning; this page has the full story.</p>
      </header>

      <div className="controls">
        <input type="search" placeholder="Search a stat, like Corsi or PDO" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search the glossary" />
        {q && <span className="count">{groups.reduce((n, g) => n + g.terms.length, 0)} explained, {list.length} labels</span>}
      </div>

      {!q && (
        <nav className="glossary-jump" aria-label="Sections">
          {GROUPS.map((g) => <a key={g.id} href={`#${g.id}`}>{g.title}</a>)}
          <a href="#all">All labels A to Z</a>
        </nav>
      )}

      {groups.map((g) => (
        <section key={g.id} id={g.id} className="glossary-group">
          <h2>{g.title}</h2>
          {g.intro && !q && <p className="glossary-intro">{g.intro}</p>}
          <dl>
            {g.terms.map((t) => (
              <div key={t.id} id={t.id} className="glossary-term">
                <dt>
                  <a href={`#${t.id}`} className="glossary-anchor" aria-label={`Link to ${t.name}`}>{t.name}</a>
                  <span className="glossary-abbr">{t.abbr}</span>
                </dt>
                <dd>
                  <p>{t.what}</p>
                  {t.read && <p className="glossary-read"><strong>How to read it:</strong> {t.read}</p>}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ))}

      <section id="all" className="glossary-group">
        <h2>All labels A to Z</h2>
        <p className="glossary-intro">Every abbreviation and column heading used in the site's tables.</p>
        {list.length === 0 && !groups.length ? (
          <p className="status">Nothing matches &ldquo;{query}&rdquo;. Try a shorter word.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Label</th><th className="left">Meaning</th></tr></thead>
              <tbody>
                {list.map(([k, v]) => <tr key={k}><td className="left"><strong>{k}</strong></td><td className="left">{v}</td></tr>)}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <p className="sub">Looking for the possession stats in context? See the <Link to="/skaters?view=possession">Possession tab on the Skaters page</Link>.</p>
    </main>
  )
}
