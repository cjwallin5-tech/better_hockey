import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { getJson } from '../lists.js'
import { hasBronze } from '../international.js'
import Medal from './Medal.jsx'
import { Skeleton } from './Skeleton.jsx'

const SHOWN = 12 // editions listed before "show all"
const AWARD_LABEL = { mvp: 'MVP', goaltender: 'Goaltender', defense: 'Defenseman', forward: 'Forward' }
const AWARD_TITLE = { mvp: 'Most valuable player', goaltender: 'Best goaltender', defense: 'Best defenseman', forward: 'Best forward' }

/** A winner's name, linked to the player's page when we can tell who it is, with the country beside it. */
function Winner({ w }) {
  if (!w) return <span className="muted">–</span>
  const name = w.player_id ? <Link to={`/${w.kind === 'goalie' ? 'goalie' : 'player'}/${w.player_id}`}>{w.name}</Link> : w.name
  return <>{name} <span className="muted">{w.code}</span></>
}

function MedalCells({ row, bronze }) {
  return (
    <>
      <td className="num">{row.gold}</td>
      <td className="num">{row.silver}</td>
      {bronze && <td className="num">{row.bronze}</td>}
    </>
  )
}

/** The Awards page's International tab: for each major national-team tournament, who won each year, a medal table by country, and the
 *  most decorated players. The tournament in view is kept in ?event=. */
export default function InternationalAwards() {
  const [params, setParams] = useSearchParams()
  const [results, setResults] = useState(null)
  const [leaders, setLeaders] = useState({ event: null, data: null })
  const [honors, setHonors] = useState({ event: null, data: null })
  const [allHonors, setAllHonors] = useState(false)
  const [all, setAll] = useState(false)
  const [error, setError] = useState(null)
  const [club, setClub] = useState(null)
  useEffect(() => {
    let ignore = false
    getJson('/api/international/triple-gold').then((d) => !ignore && setClub(d)).catch(() => {})
    getJson('/api/international/results').then((d) => !ignore && setResults(d)).catch((e) => !ignore && setError(e.message))
    return () => { ignore = true }
  }, [])
  const event = results?.tournaments.some((t) => t.id === params.get('event')) ? params.get('event') : results?.tournaments[0].id
  useEffect(() => {
    if (!event) return undefined
    let ignore = false
    getJson(`/api/international/leaders?tournament=${event}&limit=15`)
      .then((data) => !ignore && setLeaders({ event, data }))
      .catch(() => !ignore && setLeaders({ event, data: null }))
    getJson(`/api/international/awards?tournament=${event}&limit=10`)
      .then((data) => !ignore && setHonors({ event, data }))
      .catch(() => !ignore && setHonors({ event, data: null }))
    return () => { ignore = true }
  }, [event])

  if (error) return <p className="status">Couldn't load the international results: {error}</p>
  if (!results) return <Skeleton rows={8} />
  const t = results.tournaments.find((x) => x.id === event)
  const bronze = hasBronze(t.id)
  const pick = (id) => {
    const next = new URLSearchParams(params)
    next.set('event', id)
    setParams(next, { replace: true })
    setAll(false)
    setAllHonors(false)
  }
  const editions = all ? t.editions : t.editions.slice(0, SHOWN)
  const lead = leaders.event === event ? leaders.data : null
  const incomplete = lead && lead.coverage.fetched < lead.coverage.total * 0.98

  return (
    <>
      <p className="sub">
        Medals in the major men's national-team tournaments, for the players in our data. A player's medal comes from his team's finish in the
        year he played. World Cup and 4 Nations have a final but no bronze medal game, so they list a champion and a runner-up.
      </p>
      <div className="tabs" role="tablist" aria-label="Tournament">
        {results.tournaments.map((x) => (
          <button key={x.id} type="button" role="tab" aria-selected={x.id === event} className={x.id === event ? 'on' : ''} onClick={() => pick(x.id)}>{x.label}</button>
        ))}
      </div>

      <div className="home-grid">
        <section className="card">
          <h2>Medals by country</h2>
          <table className="mini">
            <thead><tr><th /><th className="num"><Medal medal="gold" /></th><th className="num"><Medal medal="silver" /></th>{bronze && <th className="num"><Medal medal="bronze" /></th>}</tr></thead>
            <tbody>
              {t.medal_table.map((c) => <tr key={c.country}><td>{c.country}</td><MedalCells row={c} bronze={bronze} /></tr>)}
            </tbody>
          </table>
        </section>

        <section className="card">
          <h2>Winners by year</h2>
          <table className="mini">
            <thead><tr><th>Year</th><th>Gold</th><th>Silver</th>{bronze && <th>Bronze</th>}</tr></thead>
            <tbody>
              {editions.map((e) => (
                <tr key={e.year}>
                  <td>{e.year}</td><td>{e.gold.name}</td><td>{e.silver.name}</td>{bronze && <td>{e.bronze?.name}</td>}
                </tr>
              ))}
            </tbody>
          </table>
          {t.editions.length > SHOWN && (
            <p className="muted small">
              <button type="button" className="link-button" onClick={() => setAll(!all)}>{all ? 'Show fewer' : `Show all ${t.editions.length} editions`}</button>
            </p>
          )}
        </section>
      </div>

      {(() => {
        const h = honors.event === event ? honors.data?.tournaments[event] : null
        if (!h) return null
        const shown = allHonors ? h.editions : h.editions.slice(0, SHOWN)
        const note = honors.data.coverage[event]
        return (
          <section className="card">
            <h2>Tournament awards</h2>
            <p className="sub">The most valuable player and the IIHF directorate awards: the best goaltender, defenseman and forward.</p>
            <div className="table-wrap">
              <table className="mini">
                <thead><tr><th>Year</th>{h.awards.map((k) => <th key={k} title={AWARD_TITLE[k]}>{AWARD_LABEL[k]}</th>)}</tr></thead>
                <tbody>
                  {shown.map((e) => (
                    <tr key={e.year}><td>{e.year}</td>{h.awards.map((k) => <td key={k}><Winner w={e.awards[k]} /></td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
            {h.editions.length > SHOWN && (
              <p className="muted small">
                <button type="button" className="link-button" onClick={() => setAllHonors(!allHonors)}>{allHonors ? 'Show fewer' : `Show all ${h.editions.length} editions`}</button>
              </p>
            )}
            {h.leaders.length > 0 && (
              <>
                <h3 className="gap">Most tournament awards</h3>
                <table className="mini">
                  <thead><tr><th>Player</th>{h.awards.map((k) => <th key={k} className="num" title={AWARD_TITLE[k]}>{AWARD_LABEL[k]}</th>)}<th className="num">Total</th></tr></thead>
                  <tbody>
                    {h.leaders.map((l) => (
                      <tr key={l.name}>
                        <td><Winner w={{ name: l.name, player_id: l.player_id, kind: l.kind }} /></td>
                        {h.awards.map((k) => <td key={k} className="num">{l[k] || ''}</td>)}<td className="num accent">{l.total}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
            {note && <p className="muted small">{note}.</p>}
          </section>
        )
      })()}

      <section className="card">
        <h2>Most decorated players{t.id === 'olympics' ? ' at the Olympics' : ` at the ${t.label}`}</h2>
        {!lead && <Skeleton rows={5} />}
        {lead && lead.players.length === 0 && <p className="status">No medalists collected yet.</p>}
        {lead && lead.players.length > 0 && (
          <div className="table-wrap">
            <table className="mini">
              <thead><tr><th>Player</th><th className="num"><Medal medal="gold" /></th><th className="num"><Medal medal="silver" /></th>{bronze && <th className="num"><Medal medal="bronze" /></th>}<th className="num">Played</th></tr></thead>
              <tbody>
                {lead.players.map((p) => (
                  <tr key={p.player_id}>
                    <td><Link to={`/${p.kind === 'goalie' ? 'goalie' : 'player'}/${p.player_id}`}>{p.name}</Link> <span className="muted">{p.position}</span>{p.active && <span className="badge">active</span>}</td>
                    <MedalCells row={p} bronze={bronze} />
                    <td className="num">{p.played}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {incomplete && (
          <p className="muted small">
            This list counts {lead.coverage.fetched.toLocaleString()} of {lead.coverage.total.toLocaleString()} players so far: the rest are still being collected, so it
            will fill in. A player's own page is always complete.
          </p>
        )}
      </section>
      {club && (
        <section className="card">
          <h2>Triple Gold Club</h2>
          <p className="sub">
            Players who have won the Stanley Cup, an Olympic gold medal and a World Championship gold medal. The year shown for each is the first time.
          </p>
          {club.members.length === 0 ? <p className="status">No members found yet.</p> : (
            <div className="table-wrap">
              <table className="mini">
                <thead><tr><th>Player</th><th className="num" title="The year of the first Stanley Cup win, and how many in all">Stanley Cup</th><th className="num" title="The year of the first Olympic gold medal">Olympic gold</th><th className="num" title="The year of the first World Championship gold medal">World Championship gold</th><th className="num" title="The year the third of the three was first won">Completed</th></tr></thead>
                <tbody>
                  {club.members.map((m) => (
                    <tr key={m.player_id}>
                      <td><Link to={`/${m.kind === 'goalie' ? 'goalie' : 'player'}/${m.player_id}`}>{m.name}</Link> <span className="muted">{m.position}</span>{m.active && <span className="badge">active</span>}</td>
                      <td className="num">{m.cup}{m.cups > 1 ? ` (${m.cups}x)` : ''}</td><td className="num">{m.olympics}</td><td className="num">{m.worlds}</td><td className="num accent">{m.completed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {club.coverage.fetched < club.coverage.total * 0.98 && (
            <p className="muted small">
              Built from {club.coverage.fetched.toLocaleString()} of {club.coverage.total.toLocaleString()} players so far: the rest are still being collected, so more
              members will appear.
            </p>
          )}
        </section>
      )}
      <p className="news-note">Results are from Wikipedia's tournament pages (CC BY-SA); built {results.built}.</p>
    </>
  )
}
