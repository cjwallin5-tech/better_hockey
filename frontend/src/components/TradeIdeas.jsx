import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { luckSummary, useLuck } from './Luck.jsx'
import { SWAP_TOLERANCE, tradeIdeas } from '../tradeIdeas.js'

const signedZ = (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(1)}`

/** Every hot and cold player in the league (skaters and goalies), as a Map id -> { z, flag, enough, goalie }. */
function useLeagueLuck() {
  const [rows, setRows] = useState(null)
  useEffect(() => {
    let ignore = false
    const get = (url, goalie) => fetch(url).then((r) => (r.ok ? r.json() : { rows: [] })).then((d) => d.rows.map((row) => [row, goalie]))
    Promise.all([
      get('/api/luck/skaters?dir=desc&limit=200', false), get('/api/luck/skaters?dir=asc&limit=200', false),
      get('/api/luck/goalies?dir=desc&limit=100', true), get('/api/luck/goalies?dir=asc&limit=100', true),
    ])
      .then((lists) => !ignore && setRows(lists.flat()))
      .catch(() => !ignore && setRows([]))
    return () => { ignore = true }
  }, [])
  return useMemo(() => (rows ? new Map(rows.map(([row, goalie]) => [row.player_id, { ...luckSummary(row, goalie), goalie }])) : null), [rows])
}

const tradeLink = (give, get) => `/fantasy?tab=trade&give=${give}&get=${get}`

/**
 * Sell-high and buy-low ideas from the luck figures: your players running above what their shots support, paired with
 * players elsewhere running below it. Only suggestions: the league's other rosters aren't known here, so a target may
 * not be on a team you can trade with.
 */
export default function TradeIdeas({ data, values, roster }) {
  const league = useLeagueLuck()
  const rosterIds = useMemo(() => roster.map((p) => p.id), [roster])
  const mine = useLuck(rosterIds)
  const names = useMemo(() => new Map([
    ...data.skaters.map((r) => [r.player_id, { name: r.name, team: r.team, pos: r.position, goalie: false }]),
    ...data.goalies.map((r) => [r.player_id, { name: r.name, team: r.team, pos: 'G', goalie: true }]),
  ]), [data])

  const ideas = useMemo(() => {
    if (!league) return null
    const luck = new Map(league)
    // your own players come from the per-player lookup, which covers everyone with enough shots, not just the extremes
    for (const [kind, goalie] of [['skaters', false], ['goalies', true]]) {
      for (const [id, row] of Object.entries(mine?.[kind] ?? {})) luck.set(Number(id), luckSummary(row, goalie))
    }
    return tradeIdeas({ values, luck, roster: new Set(rosterIds) })
  }, [league, mine, values, rosterIds])

  const who = (id) => {
    const i = names.get(id)
    return i ? <><Link to={`/${i.goalie ? 'goalie' : 'player'}/${id}`}>{i.name}</Link> <span className="muted">{i.team} · {i.pos}</span></> : `#${id}`
  }

  return (
    <section>
      <h2>Trade ideas</h2>
      <p className="sub">
        Hot players are scoring (or stopping) more than their shots and track record support, so they tend to cool off;
        cold players are due to bounce back. Value already pulls streaks toward each player's norm, so these are the
        cases where the streak is still likely to be inflating or hiding value. Targets are matched by position and must
        be worth at least {Math.round(SWAP_TOLERANCE * 100)}% of what you give. The site can't see other teams' rosters, so check a target is
        actually on a team you can trade with.
      </p>
      {!ideas ? <p className="status">Loading…</p> : (
        <>
          <h3>Sell high: your players running hot</h3>
          {roster.length === 0 ? <p className="status">Add players to your roster to see sell-high candidates.</p>
            : ideas.sell.length === 0 ? <p className="status">None of your players is running hot with a big enough sample.</p> : (
              <div className="table-wrap">
                <table>
                  <thead><tr><th className="left">Sell</th><th title="How far above expected, in standard deviations">Luck z</th><th>Value</th><th className="left">Swap for (cold, similar value)</th></tr></thead>
                  <tbody>
                    {ideas.sell.map((s) => (
                      <tr key={s.id}>
                        <td className="left">{who(s.id)}</td>
                        <td className="accent">{signedZ(s.z)}</td>
                        <td>{s.value.toFixed(1)}</td>
                        <td className="left">
                          {s.targets.length === 0 ? <span className="muted">No cold player of similar value at {s.group}</span> : s.targets.map((t) => (
                            <div key={t.id}>
                              {who(t.id)} <span className="muted">value {t.value.toFixed(1)}, z {signedZ(t.z)}</span>{' '}
                              <Link to={tradeLink(s.id, t.id)}>Analyze →</Link>
                            </div>
                          ))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

          <h3>Buy low: players not on your roster running cold</h3>
          {ideas.buy.length === 0 ? <p className="status">No cold player with positive value and a big enough sample.</p> : (
            <div className="table-wrap">
              <table>
                <thead><tr><th className="left">Player</th><th title="How far below expected, in standard deviations">Luck z</th><th>Value</th></tr></thead>
                <tbody>
                  {ideas.buy.map((b) => (
                    <tr key={b.id}>
                      <td className="left">{who(b.id)}</td>
                      <td>{signedZ(b.z)}</td>
                      <td className="accent">{b.value.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="sub">Luck is measured on <Link to="/luck">Luck &amp; regression</Link>, where the method and its limits are explained.</p>
        </>
      )}
    </section>
  )
}
