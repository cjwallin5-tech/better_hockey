import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { GOALIE_CATEGORIES, SKATER_CATEGORIES } from '../categoryDefs.js'
import { GROUPS } from '../value.js'

const rate = (v) => v.toFixed(2)
const signed = (v, d = 1) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}`

/** The categories a league counts, as definitions, for one kind of player. */
const chosen = (defs, keys) => defs.filter((d) => keys.includes(d.key))

/**
 * Every player ranked by value over the rest of the season (see value.js and categories.js). `categories` is null for a
 * points league (values are fantasy points above replacement) and the league's chosen categories for a category league
 * (values are z-scores above replacement, with each category's z shown).
 */
export default function PlayerValues({ data, values, rosterIds, onAdd, categories }) {
  const [group, setGroup] = useState('')
  const [query, setQuery] = useState('')
  const rows = useMemo(() => {
    const info = new Map([...data.skaters.map((r) => [r.player_id, r]), ...data.goalies.map((r) => [r.player_id, r])])
    const q = query.trim().toLowerCase()
    return [...values.values()]
      .filter((v) => info.has(v.id) && (!group || v.group === group) && (!q || info.get(v.id).name.toLowerCase().includes(q)))
      .sort((a, b) => a.overallRank - b.overallRank)
      .slice(0, 60)
      .map((v) => ({ v, r: info.get(v.id) }))
  }, [data, values, group, query])
  const allZero = useMemo(() => [...values.values()].every((v) => v.value === 0), [values])
  // in a category league, one column per category when a single kind of player is showing, otherwise a summary of strengths
  const cols = !categories ? null : group === 'G' ? chosen(GOALIE_CATEGORIES, categories.goalie) : group ? chosen(SKATER_CATEGORIES, categories.skater) : null
  const labelOf = new Map([...SKATER_CATEGORIES, ...GOALIE_CATEGORIES].map((d) => [d.key, d.short]))
  const strengths = (v) => Object.entries(v.z).sort((a, b) => b[1] - a[1]).slice(0, 2).filter(([, z]) => z > 0.2)
    .map(([k, z]) => `${labelOf.get(k)} ${signed(z)}`).join(', ')

  return (
    <section>
      <h2>Player values</h2>
      <p className="sub">
        {categories
          ? `Each player's worth over the rest of the season in your categories: how far above the rostered pool they are in each category you count, added up as z-scores, minus the best player at their position you could pick up for free. A player at replacement level is worth 0. The z-scores are measured against how much real outcomes vary, so a mostly-luck category (shutouts, save %) moves values little, and values start small early in the season and grow as the sample does.`
          : `Each player's worth over the rest of the season, in fantasy points above the best player at their position you could pick up for free, using your league scoring and size (Scoring & backup tab). A player at replacement level is worth 0. Early in the season a short sample is pulled toward the player's own record from the last two seasons (rookies toward the position average), so a hot week doesn't read as a new talent level.`}
        {' '}Games left are scaled by how often the player has played. It can't see injuries or role changes still to come.
      </p>
      {categories && categories.skater.length + categories.goalie.length === 0 && (
        <p className="notice">No categories are selected, so everyone is worth 0. Pick your categories in the Scoring &amp; backup tab.</p>
      )}
      {!categories && allZero && <p className="notice">Your scoring gives every stat 0 points, so everyone is worth 0. Set your league scoring first.</p>}
      <div className="h2h-picks">
        <label className="h2h-pick">Position
          <select value={group} onChange={(e) => setGroup(e.target.value)}>
            <option value="">All</option>
            {GROUPS.map((g) => <option key={g} value={g}>{g === 'G' ? 'Goalies' : g}</option>)}
          </select>
        </label>
        <label className="h2h-pick">Search
          <input type="search" value={query} placeholder="Player name" onChange={(e) => setQuery(e.target.value)} />
        </label>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th><th className="left">Player</th><th className="left">Team</th><th className="left">Pos</th><th>GP</th>
              {!categories && (
                <>
                  <th title="Fantasy points per game so far">FP/GP</th>
                  <th title="The rate we expect going forward, after pulling a short sample toward the player's record or the average">Expected FP/GP</th>
                  <th title="Expected rate minus the replacement level at the position">vs replacement</th>
                </>
              )}
              <th>Games left</th>
              {categories && (cols
                ? cols.map((d) => <th key={d.key} title={`${d.label}: z-score${d.sign < 0 ? ' (lower is better, so fewer is positive)' : ''}`}>{d.short}</th>)
                : <th className="left" title="The categories where the player is furthest above the pool">Strengths (z)</th>)}
              <th title={categories ? 'Total z-score above replacement over the rest of the season' : 'Fantasy points above replacement over the rest of the season'}>Value</th><th />
            </tr>
          </thead>
          <tbody>
            {rows.map(({ v, r }) => (
              <tr key={v.id}>
                <td>{v.overallRank}</td>
                <td className="left">
                  <Link to={`/${v.kind === 'goalie' ? 'goalie' : 'player'}/${v.id}`}>{r.name}</Link>
                  {v.kind === 'skater' && !v.hasHistory && <span className="badge" title="No recent seasons on file, so the early rate is pulled toward the position average">new</span>}
                </td>
                <td className="left">{v.team}</td><td className="left">{v.group}</td><td>{v.gp}</td>
                {!categories && <><td>{rate(v.rate)}</td><td>{rate(v.shrunk)}</td><td>{signed(v.above, 2)}</td></>}
                <td>{v.expectedGames.toFixed(0)}</td>
                {categories && (cols ? cols.map((d) => <td key={d.key}>{signed(v.z[d.key] ?? 0)}</td>) : <td className="left">{strengths(v) || '–'}</td>)}
                <td className="accent">{signed(v.value, categories ? 1 : 0)}</td>
                <td>{rosterIds.has(v.id) ? <span className="muted">on your team</span> : <button className="link-button" onClick={() => onAdd({ player_id: v.id, name: r.name }, v.kind)}>Add</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && <p className="status">No players match.</p>}
    </section>
  )
}
