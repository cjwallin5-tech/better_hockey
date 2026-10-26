import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { RoleBadge } from './Roles.jsx'
import { SORTS, luckById, scheduleByTeam, waiverRows } from '../waiver.js'
import { describe } from '../glossary.js'
import { fmt1 } from '../format.js'

const POSITIONS = {
  skater: [['all', 'All skaters'], ['F', 'Forwards'], ['C', 'Centers'], ['L', 'Left wings'], ['R', 'Right wings'], ['D', 'Defensemen']],
  goalie: [['all', 'All goalies']],
}
const LIMIT = 40
const ok = (r) => (r.ok ? r.json() : null)

/** Roles, luck and the week's schedule for the waiver wire. Each source fails on its own: the table still works without it. */
function useSignals(kind) {
  const [state, setState] = useState({ kind: null, roles: null, luck: null, schedule: null })
  useEffect(() => {
    let ignore = false
    const skater = kind === 'skater'
    const get = (url) => fetch(url).then(ok).catch(() => null)
    Promise.all([
      skater ? get('/api/roles/changes?dir=up&window=5&limit=200') : null,
      get(`/api/luck/${skater ? 'skaters' : 'goalies'}?dir=asc&limit=200`),
      get(`/api/luck/${skater ? 'skaters' : 'goalies'}?dir=desc&limit=200`),
      get('/api/matchups/schedule?days=7'),
    ]).then(([roles, cold, hot, schedule]) => {
      if (ignore) return
      setState({
        kind,
        roles: new Map((roles?.rows ?? []).map((r) => [r.player_id, r])),
        luck: luckById(cold, hot),
        schedule: scheduleByTeam(schedule, kind),
      })
    })
    return () => { ignore = true }
  }, [kind])
  return state.kind === kind ? state : null
}

const gamesTitle = (r) => (r.games == null ? '' : `${r.games} games in the next 7 days${r.ratio != null ? `; average matchup rating ${r.ratio.toFixed(2)} (above 1 is soft)` : ''}`)

/**
 * Players not on your roster, with the reasons to pick one up: value over the rest of the season in your league, a bigger
 * role, a hot stretch, results below what the shots support, and games this week.
 */
export default function WaiverWire({ data, kind, values, rosterIds, league, onAdd }) {
  const [sort, setSort] = useState('value')
  const [position, setPosition] = useState('all')
  const [search, setSearch] = useState('')
  const [likelyAvailable, setLikelyAvailable] = useState(true)
  const [hideHurt, setHideHurt] = useState(true)
  const [showAll, setShowAll] = useState(false)
  const signals = useSignals(kind)
  const goalie = kind === 'goalie'

  const rows = useMemo(() => {
    if (!values || !signals) return null
    return waiverRows({
      kind, players: goalie ? data.goalies : data.skaters, values, roles: signals.roles, luck: signals.luck, schedule: signals.schedule,
      roster: rosterIds, league, filters: { position: goalie ? 'all' : position, search, likelyAvailable, hideHurt }, sort,
    })
  }, [kind, goalie, data, values, signals, rosterIds, league, position, search, likelyAvailable, hideHurt, sort])

  const sorts = SORTS.filter((s) => !(goalie && (s.id === 'role')))
  const activeSort = sorts.find((s) => s.id === sort) ?? sorts[0]
  const shown = rows ? (showAll ? rows : rows.slice(0, LIMIT)) : []

  return (
    <section>
      <h2>Waiver wire: {goalie ? 'goalies' : 'skaters'}</h2>
      <p className="sub">
        Players not on your roster. Value is over the rest of the season in your league settings (0 is a replacement-level player you could always find).
        {' '}{activeSort.hint}.
      </p>
      <div className="tabs" role="tablist" aria-label="Sort the waiver wire">
        {sorts.map((s) => (
          <button key={s.id} role="tab" aria-selected={s.id === sort} className={s.id === sort ? 'on' : ''} title={s.hint} onClick={() => { setSort(s.id); setShowAll(false) }}>{s.label}</button>
        ))}
      </div>
      <div className="h2h-picks">
        {!goalie && (
          <label className="h2h-pick">Position
            <select value={position} onChange={(e) => setPosition(e.target.value)}>
              {POSITIONS.skater.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
        )}
        <label className="h2h-pick">Search
          <input type="search" placeholder="Player name" value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
        <label className="h2h-pick">
          <span><input type="checkbox" checked={likelyAvailable} onChange={(e) => setLikelyAvailable(e.target.checked)} /> Likely available only</span>
        </label>
        <label className="h2h-pick">
          <span><input type="checkbox" checked={hideHurt} onChange={(e) => setHideHurt(e.target.checked)} /> Hide players who are out</span>
        </label>
      </div>
      {likelyAvailable && (
        <p className="sub small">
          Hides the best players at each position by value (as many as a league of {league.teams} teams starts), who are probably already rostered.
          We can't see who is actually owned in your league.
        </p>
      )}

      {!rows && <p className="status">Loading…</p>}
      {rows && rows.length === 0 && <p className="status">No players match. Try turning off a filter{sort === 'buy' ? ', or pick another sort: no one available is running cold right now' : ''}.</p>}
      {rows && rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="left">Player</th><th className="left" title={describe('Team')}>Team</th><th title={describe('GP')}>GP</th>
                <th title="Value over the rest of the season in your league">Value</th>
                <th title={goalie ? describe('Recent GSAA') : 'Point pace over recent games, per 84'}>{goalie ? 'Recent GSAA' : 'Recent pace'}</th>
                {!goalie && <th title="Power-play and ice-time changes over the last 5 games">Role</th>}
                <th title="Games in the next 7 days">Games</th>
                <th className="left">Notes</th><th />
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id}>
                  <td className="left">
                    <Link to={`/${goalie ? 'goalie' : 'player'}/${r.id}`}>{r.name}</Link>
                    <span className="muted"> {r.position}</span>
                  </td>
                  <td className="left">{r.team}</td><td>{r.gp}</td>
                  <td className="accent">{r.value.toFixed(1)}</td>
                  <td>{r.form == null ? '–' : fmt1(r.form)}</td>
                  {!goalie && <td>{r.role ? <RoleBadge row={r.role} /> : '–'}</td>}
                  <td title={gamesTitle(r)}>{r.games ?? '–'}</td>
                  <td className="left">
                    {r.hurt && <span className="badge warn" title="Not in the team's last games">out {r.gamesOut}</span>}
                    {r.hot && <span className="badge" title="Recent point pace is well above the season pace">hot stretch</span>}
                    {r.luck?.flag === 'cold' && <span className="badge" title={goalie ? 'Saving fewer than the shots faced should allow: likely to improve' : 'Scoring below what the shots and chances support: likely to rebound'}>due</span>}
                    {r.luck?.flag === 'hot' && <span className="badge warn" title={goalie ? 'Saving more than the shots faced should allow: may cool off' : 'Scoring above what the shots and chances support: may cool off'}>running hot</span>}
                    {r.likelyOwned && <span className="badge warn" title="Ranks high enough that a league your size has probably rostered this player">likely owned</span>}
                  </td>
                  <td><button className="link-button" onClick={() => onAdd({ player_id: r.id, name: r.name }, kind)}>Add</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {rows && rows.length > LIMIT && (
        <p><button className="link-button" onClick={() => setShowAll((v) => !v)}>{showAll ? `Show the top ${LIMIT}` : `Show all ${rows.length}`}</button></p>
      )}
    </section>
  )
}
