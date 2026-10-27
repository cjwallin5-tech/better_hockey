import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { findTrades } from '../tradefinder.js'

const signed = (v, d = 1) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(d)}`

/**
 * Trades that make both you and another team in your league better, from everyone's rosters and the player values (see
 * tradefinder.js). `values` is the Map from value.js / categories.js; `info` maps id -> { name, team, position }; slots are your
 * league's starting slots. league is the active private league (teams and rosters), or null.
 */
export default function TradePartners({ league, roster, values, info, slots, isCats }) {
  const [team, setTeam] = useState('all')
  const [sort, setSort] = useState('mine')
  const [both, setBoth] = useState(true)
  const unit = isCats ? 'z' : 'pts'

  const others = useMemo(() => (league?.teams ?? []).filter((t) => !t.mine), [league])
  const trades = useMemo(() => {
    if (!league || !values) return []
    return findTrades({
      mine: roster.map((p) => p.id), teams: team === 'all' ? others : others.filter((t) => String(t.id) === team),
      values, slots, requireBoth: both, sort, limit: 25,
    })
  }, [league, values, roster, others, team, slots, both, sort])

  if (!league) {
    return (
      <section>
        <h2>Trade partners</h2>
        <p className="status">This looks for trades that help both you and another team in your league, so it needs their rosters. <Link to="/leagues">Start or join a league</Link> and pick it on this page.</p>
      </section>
    )
  }
  const nameOf = (id) => info.get(id)?.name ?? String(id)
  const line = (id) => {
    const v = values.get(id)
    return (
      <li key={id}>
        <Link to={`/${info.get(id)?.kind === 'goalie' ? 'goalie' : 'player'}/${id}`}>{nameOf(id)}</Link>{' '}
        <span className="muted">{v?.group} · value {v ? signed(v.value) : '–'} {unit}</span>
      </li>
    )
  }
  const empty = others.filter((t) => t.players.length === 0)

  return (
    <section>
      <h2>Trade partners in {league.name}</h2>
      <p className="sub">
        Trades that look good to you and to the other team, judged by lineup value: only the players who start count, so a team with a spare
        center gains from a winger and the other way round. Each suggestion lists what changes for both lineups. This is the model's view of
        fair: it can't see injuries, keepers, who a manager likes or why someone is on their bench, and early-season values are noisy, so treat
        these as conversation starters. Values are over the rest of the season in {isCats ? 'category z-scores' : 'fantasy points'}.
      </p>
      <div className="h2h-picks">
        <label className="h2h-pick">Partner
          <select value={team} onChange={(e) => setTeam(e.target.value)}>
            <option value="all">Every team</option>
            {others.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </label>
        <label className="h2h-pick">Order by
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="mine">Biggest gain for me</option>
            <option value="balanced">Fairest to both</option>
          </select>
        </label>
        <label className="h2h-pick">
          <span><input type="checkbox" checked={both} onChange={(e) => setBoth(e.target.checked)} /> Only trades that help them too</span>
        </label>
      </div>
      {roster.length === 0 && <p className="status">Add players to your team first (Roster tab).</p>}
      {empty.length > 0 && <p className="muted">No roster yet for {empty.map((t) => t.name).join(', ')}, so no trades are shown with them.</p>}
      {roster.length > 0 && trades.length === 0 && <p className="status">No trade found. {both ? 'Try turning off "Only trades that help them too" to see one-sided ones.' : ''}</p>}
      {trades.map((t, i) => (
        <div key={`${t.team.id}-${i}`} className="card" style={{ marginBottom: 12 }}>
          <h3 style={{ marginTop: 0 }}>With {t.team.name}</h3>
          <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
            <div><strong>You give</strong><ul className="plain-list">{t.give.map(line)}</ul></div>
            <div><strong>You get</strong><ul className="plain-list">{t.get.map(line)}</ul></div>
          </div>
          <p>
            Your lineup <strong className="accent">{signed(t.gainMine)} {unit}</strong>
            {t.startsMine.length > 0 && <span className="muted"> ({t.startsMine.map(nameOf).join(', ')} would start for you)</span>}.{' '}
            Theirs <strong>{signed(t.gainTheirs)} {unit}</strong>
            {t.startsTheirs.length > 0 && <span className="muted"> ({t.startsTheirs.map(nameOf).join(', ')} would start for them)</span>}.
          </p>
          <p><Link to={`/fantasy?tab=trade&give=${t.give.join(',')}&get=${t.get.join(',')}`}>Open in the trade analyzer</Link></p>
        </div>
      ))}
    </section>
  )
}
