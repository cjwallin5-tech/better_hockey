import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { GROUPS, teamOf } from '../value.js'
import { buildBoard, keeperRows, myPicks, needs, recommend, roundOf, slotAt, tierCliffs } from '../draft.js'

const KEY = 'nhl-stats.fantasy-draft'
const LIMIT = 50
const GROUP_NAMES = { C: 'Center', L: 'Left wing', R: 'Right wing', D: 'Defense', G: 'Goalie' }

function read() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? 'null')
    return {
      picks: (Array.isArray(raw?.picks) ? raw.picks : []).filter((p) => p && Number.isInteger(p.id)).map((p) => ({ id: p.id, mine: Boolean(p.mine) })),
      slot: Number.isInteger(raw?.slot) && raw.slot >= 1 ? raw.slot : 1,
      snake: raw?.snake !== false,
      keepers: raw?.keepers && typeof raw.keepers === 'object' ? raw.keepers : {},
      maxKeepers: Number.isInteger(raw?.maxKeepers) && raw.maxKeepers >= 0 ? raw.maxKeepers : 3,
    }
  } catch {
    return { picks: [], slot: 1, snake: true, keepers: {}, maxKeepers: 3 }
  }
}

const signed = (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(1)}`

/**
 * Draft board and keeper values. data: { skaters, goalies } season rows; values: the Map from value.js / categories.js;
 * league: the cleaned league ({ teams, slots, format }); roster: your fantasy roster, for the keeper table.
 * The draft is tracked by hand: mark each pick as yours or someone else's as it happens.
 */
export default function DraftHelper({ data, values, league, roster }) {
  const [state, setState] = useState(read)
  const [position, setPosition] = useState('all')
  const [search, setSearch] = useState('')
  const isCats = league.format === 'categories'
  const unit = isCats ? 'z' : 'pts'
  const save = (next) => {
    setState(next)
    try {
      localStorage.setItem(KEY, JSON.stringify(next))
    } catch {
      // storage unavailable: the draft simply won't be remembered
    }
  }

  const info = useMemo(() => {
    const m = new Map()
    for (const r of data.skaters) m.set(r.player_id, { name: r.name, team: teamOf(r), position: r.position, kind: 'skater' })
    for (const r of data.goalies) m.set(r.player_id, { name: r.name, team: teamOf(r), position: 'G', kind: 'goalie' })
    return m
  }, [data])
  const board = useMemo(() => buildBoard({ values, info, league }), [values, info, league])

  const slot = Math.min(state.slot, league.teams)
  const taken = useMemo(() => new Set(state.picks.map((p) => p.id)), [state.picks])
  const available = useMemo(() => board.filter((r) => !taken.has(r.id)), [board, taken])
  const byId = useMemo(() => new Map(board.map((r) => [r.id, r])), [board])
  const mine = state.picks.filter((p) => p.mine).map((p) => byId.get(p.id)).filter(Boolean)
  const open = needs(mine.map((r) => r.group), league.slots)
  const rec = recommend(available, open)
  const cliffs = tierCliffs(available)

  const next = state.picks.length + 1
  const onClock = slotAt(next, league.teams, state.snake)
  const upcoming = myPicks({ slot, teams: league.teams, snake: state.snake, from: next, count: 3 })
  const shown = available
    .filter((r) => (position === 'all' || r.group === position) && (!search.trim() || r.name.toLowerCase().includes(search.trim().toLowerCase())))
    .slice(0, LIMIT)

  const pick = (id, isMine) => save({ ...state, picks: [...state.picks, { id, mine: isMine }] })
  const undo = () => save({ ...state, picks: state.picks.slice(0, -1) })
  const reset = () => save({ ...state, picks: [] })

  // keepers: your roster with the round each would cost
  const candidates = roster.map((p) => ({ id: p.id, round: Number(state.keepers[p.id]) }))
  const keepers = useMemo(
    () => keeperRows(candidates, board, league.teams, state.maxKeepers),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [JSON.stringify(candidates), board, league.teams, state.maxKeepers],
  )
  const setRound = (id, v) => save({ ...state, keepers: { ...state.keepers, [id]: v === '' ? undefined : Number(v) } })

  if (board.length === 0 || board[0].value <= 0) {
    return (
      <section>
        <h2>Draft helper</h2>
        <p className="status">No player values yet. They come from the games left this season, so the board fills in once the new season has games played.</p>
      </section>
    )
  }

  return (
    <section>
      <h2>Draft helper</h2>
      <p className="sub">
        Everyone ranked by value over the best free pickup in your league ({league.teams} teams; {GROUPS.filter((g) => league.slots[g]).map((g) => `${league.slots[g]} ${g}`).join(', ')}),
        in {isCats ? 'category z-scores' : 'fantasy points'} over the rest of this season, so a center and a goalie share one scale.
        Tiers group players who are close in value: the drop after a tier is the reason to take one now. Track the draft by hand
        (Mine or Taken on each pick); the board and your needs update. It knows nothing about injuries or what other managers
        will do, and players with no games played yet aren't listed.
      </p>

      <div className="h2h-picks">
        <label className="h2h-pick">Your draft slot
          <input type="number" min="1" max={league.teams} value={slot} style={{ minWidth: 80, width: 80 }}
                 onChange={(e) => save({ ...state, slot: Math.max(1, Math.min(league.teams, Math.round(Number(e.target.value)) || 1)) })} />
        </label>
        <label className="h2h-pick" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <input type="checkbox" checked={state.snake} onChange={(e) => save({ ...state, snake: e.target.checked })} /> Snake draft
        </label>
      </div>

      <p>
        Pick <strong>{next}</strong> (round {roundOf(next, league.teams)}):{' '}
        {onClock === slot ? <strong className="accent">you are on the clock</strong> : <>team {onClock} is on the clock</>}.
        {upcoming.length > 0 && <> Your next picks: {upcoming.map((n) => `#${n} (round ${roundOf(n, league.teams)})`).join(', ')}.</>}
      </p>

      {rec.best && (
        <p>
          Best available: <strong>{rec.best.name}</strong> ({rec.best.position}, {signed(rec.best.value)} {unit}).
          {rec.forNeed && rec.forNeed.id !== rec.best.id && <> Best at a position you still need: <strong>{rec.forNeed.name}</strong> ({rec.forNeed.position}, {signed(rec.forNeed.value)} {unit}).</>}
          {' '}Open starting slots: {GROUPS.map((g) => `${g} ${open[g]}`).join(', ')}.
        </p>
      )}
      <ul className="roster-alerts">
        {GROUPS.filter((g) => cliffs[g]).map((g) => (
          <li key={g}>
            {GROUP_NAMES[g]}: {cliffs[g].left} left in tier {cliffs[g].tier}
            {cliffs[g].drop != null && <>, then a drop of {cliffs[g].drop.toFixed(1)} {unit}</>}
          </li>
        ))}
      </ul>

      <div className="h2h-picks">
        <label className="h2h-pick">Position
          <select value={position} onChange={(e) => setPosition(e.target.value)}>
            <option value="all">All</option>
            {GROUPS.map((g) => <option key={g} value={g}>{GROUP_NAMES[g]}</option>)}
          </select>
        </label>
        <label className="h2h-pick">Search
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th><th className="left">Player</th><th>Pos</th><th className="left">Team</th>
              <th title="Players in a tier are close in value">Tier</th>
              <th title={`Value over the best free pickup at the position, in ${isCats ? 'z-scores' : 'fantasy points'}`}>Value</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id}>
                <td>{r.overall}</td>
                <td className="left"><Link to={`/${r.kind === 'goalie' ? 'goalie' : 'player'}/${r.id}`}>{r.name}</Link></td>
                <td>{r.group}</td><td className="left">{r.team}</td><td>{r.tier}</td>
                <td className="accent">{signed(r.value)}</td>
                <td>
                  <button className="link-button" onClick={() => pick(r.id, true)}>Mine</button>{' '}
                  <button className="link-button" onClick={() => pick(r.id, false)}>Taken</button>
                </td>
              </tr>
            ))}
            {shown.length === 0 && <tr><td colSpan={7} className="left muted">Nobody matches.</td></tr>}
          </tbody>
        </table>
      </div>

      <h3>Your picks ({mine.length}) and the draft so far ({state.picks.length})</h3>
      <p>
        {mine.length ? mine.map((r) => `${r.name} (${r.group})`).join(', ') : 'No picks of yours yet.'}
      </p>
      <p>
        <button className="link-button" onClick={undo} disabled={state.picks.length === 0}>Undo last pick</button>{' '}
        <button className="link-button" onClick={() => { if (window.confirm('Clear every pick?')) reset() }} disabled={state.picks.length === 0}>Reset draft</button>
      </p>

      <h3>Keepers</h3>
      <p className="muted">
        For a keeper league: enter the round each of your players would cost to keep. The surplus is his value minus the value of the
        player who typically goes at the middle of that round, and the best surpluses up to your keeper limit are marked keep.
      </p>
      <div className="h2h-picks">
        <label className="h2h-pick">Keepers allowed
          <input type="number" min="0" max="20" value={state.maxKeepers} style={{ minWidth: 80, width: 80 }}
                 onChange={(e) => save({ ...state, maxKeepers: Math.max(0, Math.round(Number(e.target.value)) || 0) })} />
        </label>
      </div>
      {roster.length === 0 ? <p className="status">Add players to your team (Roster tab) to price keepers.</p> : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="left">Player</th><th title="The draft round he would cost to keep">Round</th>
                <th>Value</th><th title="Value of the player who typically goes in the middle of that round">Round value</th><th>Surplus</th><th />
              </tr>
            </thead>
            <tbody>
              {roster.map((p) => {
                const row = keepers.find((k) => k.id === p.id)
                return (
                  <tr key={p.id}>
                    <td className="left"><Link to={`/${p.kind === 'goalie' ? 'goalie' : 'player'}/${p.id}`}>{p.name}</Link></td>
                    <td>
                      <input type="number" min="1" max="30" value={state.keepers[p.id] ?? ''} placeholder="–" style={{ minWidth: 60, width: 60 }}
                             onChange={(e) => setRound(p.id, e.target.value)} />
                    </td>
                    {row ? (
                      <>
                        <td>{signed(row.value)}</td><td>{signed(row.typical)}</td>
                        <td className={row.surplus > 0 ? 'accent' : 'muted'}>{signed(row.surplus)}</td>
                        <td>{row.keep ? <strong className="accent">Keep</strong> : <span className="muted">{row.surplus > 0 ? 'Over the limit' : 'Let go'}</span>}</td>
                      </>
                    ) : <td colSpan={4} className="muted">{byId.has(p.id) ? 'Enter a round' : 'No value yet'}</td>}
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
