import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { GOALIE_CATEGORIES, SKATER_CATEGORIES } from '../categoryDefs.js'
import { tradeSummary } from '../value.js'
import { LuckBadge, useLuck } from './Luck.jsx'
import { RoleBadge, useRoles } from './Roles.jsx'
import { describe } from '../glossary.js'
import ShareButtons from './ShareButtons.jsx'

const signedZ = (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(1)}`
const signed = (v, d = 0) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}`

function Picker({ pool, taken, onPick, placeholder }) {
  const [query, setQuery] = useState('')
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return []
    return pool.filter((p) => p.name.toLowerCase().includes(q) && !taken.has(p.id)).slice(0, 8)
  }, [query, pool, taken])
  return (
    <div className="search-box">
      <input type="search" placeholder={placeholder} value={query} onChange={(e) => setQuery(e.target.value)} />
      {matches.length > 0 && (
        <ul className="results">
          {matches.map((m) => (
            <li key={m.id}>
              <button onClick={() => { onPick(m.id); setQuery('') }}>{m.name} <span>{m.team} · {m.pos}</span></button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Side({ title, ids, setIds, side, pool, taken, info, luck, roles, rosterOptions, cats }) {
  const remove = (id) => setIds(ids.filter((x) => x !== id))
  return (
    <div className="trade-side">
      <h3>{title}</h3>
      <Picker pool={pool} taken={taken} onPick={(id) => setIds([...ids, id])} placeholder="Search any player…" />
      {rosterOptions && rosterOptions.length > 0 && (
        <select value="" onChange={(e) => e.target.value && setIds([...ids, Number(e.target.value)])} aria-label="Add from your roster">
          <option value="">…or pick from your roster</option>
          {rosterOptions.filter((p) => !taken.has(p.id)).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      )}
      {ids.length === 0 && <p className="status">No players yet.</p>}
      {ids.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              {cats
                ? <tr><th className="left">Player</th><th className="left" title={describe('Pos')}>Pos</th><th title={describe('Games left')}>Games left</th><th title="Total z-score above replacement over the rest of the season">Value</th><th /></tr>
                : <tr><th className="left">Player</th><th className="left" title={describe('Pos')}>Pos</th><th title={describe('Expected FP/GP')}>Expected FP/GP</th><th title={describe('Games left')}>Games left</th><th title={describe('Projected FP')}>Projected FP</th><th title={describe('Value')}>Value</th><th /></tr>}
            </thead>
            <tbody>
              {ids.map((id) => {
                const v = side.players.find((p) => p.id === id)
                const i = info.get(id)
                return (
                  <tr key={id}>
                    <td className="left">
                      <Link to={`/${i.kind === 'goalie' ? 'goalie' : 'player'}/${id}`}>{i.name}</Link>
                      {i.kind === 'skater' && <RoleBadge row={roles?.[id]} />}
                      <LuckBadge row={luck?.[i.kind === 'goalie' ? 'goalies' : 'skaters']?.[id]} goalie={i.kind === 'goalie'} />
                    </td>
                    {v ? (cats ? (
                      <>
                        <td className="left">{v.group}</td><td>{v.expectedGames.toFixed(0)}</td><td className="accent">{signedZ(v.value)}</td>
                      </>
                    ) : (
                      <>
                        <td className="left">{v.group}</td><td>{v.shrunk.toFixed(2)}</td><td>{v.expectedGames.toFixed(0)}</td>
                        <td>{v.projected.toFixed(0)}</td><td className="accent">{signed(v.value)}</td>
                      </>
                    )) : <td className="left" colSpan={cats ? 3 : 5}><span className="muted">No games played yet</span></td>}
                    <td><button className="link-button" onClick={() => remove(id)}>Remove</button></td>
                  </tr>
                )
              })}
            </tbody>
            <tfoot>
              {cats
                ? <tr><td className="left">Total</td><td /><td /><td className="accent">{signedZ(side.value)}</td><td /></tr>
                : <tr><td className="left">Total</td><td /><td /><td /><td>{side.projected.toFixed(0)}</td><td className="accent">{signed(side.value)}</td><td /></tr>}
            </tfoot>
          </table>
        </div>
      )}
    </div>
  )
}

/**
 * "I give A and B, I get C": each side's value over the rest of the season under your scoring, and what the trade does
 * to you. Hot/cold badges (luck) and role-change badges show what the raw numbers don't.
 */
export default function TradeAnalyzer({ data, values, roster, categories }) {
  const [params, setParams] = useSearchParams()
  const idList = (key) => (params.get(key) ?? '').split(',').map(Number).filter(Boolean)
  // the picks live in the URL (?give=1,2&get=3) so a trade can be shared; read once, then written back on change
  const [give, setGive] = useState(() => idList('give'))
  const [get, setGet] = useState(() => idList('get'))
  const info = useMemo(() => new Map([
    ...data.skaters.map((r) => [r.player_id, { id: r.player_id, kind: 'skater', name: r.name, team: r.team, pos: r.position }]),
    ...data.goalies.map((r) => [r.player_id, { id: r.player_id, kind: 'goalie', name: r.name, team: r.team, pos: 'G' }]),
  ]), [data])
  const pool = useMemo(() => [...info.values()], [info])
  const taken = useMemo(() => new Set([...give, ...get]), [give, get])
  const t = useMemo(() => tradeSummary(give, get, values), [give, get, values])
  useEffect(() => {
    const next = new URLSearchParams(params)
    for (const [key, ids] of [['give', give], ['get', get]]) {
      if (ids.length) next.set(key, ids.join(','))
      else next.delete(key)
    }
    if (next.toString() !== params.toString()) setParams(next, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [give, get])
  const luck = useLuck([...give, ...get])
  const roles = useRoles([...give, ...get].filter((id) => info.get(id)?.kind === 'skater'))
  const rosterOptions = roster.filter((p) => info.has(p.id)).map((p) => ({ id: p.id, name: info.get(p.id).name }))

  const larger = Math.max(Math.abs(t.give.value), Math.abs(t.get.value))
  // about even: under 5 points of value in a points league, under a third of a z-score in a category league (or 5% of the bigger side)
  const even = Math.abs(t.net) < Math.max(categories ? 0.3 : 5, 0.05 * larger)
  const catRows = categories
    ? [...SKATER_CATEGORIES.filter((d) => categories.skater.includes(d.key)), ...GOALIE_CATEGORIES.filter((d) => categories.goalie.includes(d.key))]
        .filter((d) => d.key in t.give.z || d.key in t.get.z)
    : []
  const ready = give.length > 0 && get.length > 0
  const verdict = even
    ? 'About even'
    : categories
      ? (t.net > 0 ? `Gain about ${signedZ(t.net)} of value` : `Give up about ${signedZ(Math.abs(t.net))} of value`)
      : (t.net > 0 ? `Gain about ${signed(t.net)} points of value` : `Give up about ${signed(Math.abs(t.net))} points of value`)
  const names = (ids) => ids.map((id) => info.get(id)?.name).filter(Boolean).join(', ')
  const card = ready && {
    title: 'Trade check',
    subtitle: `Give ${names(give)}  |  Get ${names(get)}`,
    columns: ['You give', 'You get', 'Net'],
    rows: categories
      ? catRows.map((d) => {
          const g = t.give.z[d.key] ?? 0
          const r = t.get.z[d.key] ?? 0
          return { label: d.label, cells: [signedZ(g), signedZ(r), signedZ(r - g)], best: r - g >= 0 ? 2 : null }
        })
      : [
          { label: 'Projected points', cells: [t.give.projected.toFixed(0), t.get.projected.toFixed(0), signed(t.netProjected)], best: null },
          { label: 'Value over the rest of the season', cells: [signed(t.give.value), signed(t.get.value), signed(t.net)], best: 2 },
        ],
    verdict,
    footer: 'Value is over a replacement-level free agent for the rest of the season, under my league settings.',
  }
  const sizeNote = give.length !== get.length
    ? `You give ${give.length} and get ${get.length}: ${give.length > get.length ? 'the extra open roster spots' : 'the extra players need roster spots, and whoever you drop'} would be filled by a replacement-level pickup, who is worth 0 here, so it is already counted.`
    : null

  return (
    <section>
      <h2>Trade analyzer</h2>
      <p className="sub">
        {categories
          ? 'Value is the total z-score above the best free player at the same position over the rest of the season, across the categories your league counts (see Player values for how it is estimated). The category table shows where you gain and lose. '
          : 'Value is fantasy points above the best free player at the same position over the rest of the season, under your scoring and league (see Player values for how it is estimated). '}
        Hot and cold badges show who is running above or below what their shots
        predict, and role badges show recent power-play or ice-time moves, neither of which is in the value itself.
      </p>
      <div className="trade-grid">
        <Side title="You give" ids={give} setIds={setGive} side={t.give} pool={pool} taken={taken} info={info} luck={luck} roles={roles} rosterOptions={rosterOptions} cats={Boolean(categories)} />
        <Side title="You get" ids={get} setIds={setGet} side={t.get} pool={pool} taken={taken} info={info} luck={luck} roles={roles} cats={Boolean(categories)} />
      </div>
      {ready ? (
        <div className="notice" role="status">
          <strong>
            {even
              ? 'About even'
              : categories
                ? (t.net > 0 ? `You gain about ${signedZ(t.net)} of value` : `You give up about ${signedZ(Math.abs(t.net))} of value`)
                : (t.net > 0 ? `You gain about ${signed(t.net)} points of value` : `You give up about ${signed(Math.abs(t.net))} points of value`)}
          </strong>
          {even ? ` (${categories ? signedZ(t.net) : signed(t.net)} over the rest of the season).` : ' over the rest of the season.'}
          {!categories && <> Projected points: {t.give.projected.toFixed(0)} out, {t.get.projected.toFixed(0)} in.</>}
          {sizeNote && <><br />{sizeNote}</>}
        </div>
      ) : <p className="status">Add at least one player to each side to compare.</p>}
      {ready && <ShareButtons card={card} filename="trade-check.png" />}
      {ready && catRows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th className="left">Category</th><th>You give</th><th>You get</th><th title={describe('Net')}>Net</th></tr></thead>
            <tbody>
              {catRows.map((d) => {
                const give = t.give.z[d.key] ?? 0
                const get = t.get.z[d.key] ?? 0
                return (
                  <tr key={d.key}>
                    <td className="left">{d.label}</td><td>{signedZ(give)}</td><td>{signedZ(get)}</td>
                    <td className={get - give >= 0 ? 'accent' : ''}>{signedZ(get - give)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
