import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { buildEntries } from '../lineup.js'
import { matchNames, teamWeek, winChance } from '../h2h.js'

const KEY = 'nhl-stats.fantasy-opponent'
const dayName = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short' })
const ok = (r) => (r.ok ? r.json() : null)

function readOpponent() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? 'null')
    const players = (Array.isArray(raw?.players) ? raw.players : []).filter((p) => p && Number.isInteger(p.id) && (p.kind === 'skater' || p.kind === 'goalie') && typeof p.name === 'string')
    return { name: typeof raw?.name === 'string' ? raw.name : '', players }
  } catch {
    return { name: '', players: [] }
  }
}

function saveOpponent(next) {
  try {
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    // storage unavailable: the opponent simply won't be remembered
  }
}

/** Who contributes most to a team's week, as "Name 12.3" items. */
const Contributors = ({ starters }) => (
  <p className="muted">{starters.slice(0, 5).map((s) => `${s.name} ${s.score.toFixed(1)}`).join(' · ') || 'No starts'}</p>
)

/**
 * Your next 7 days against another team in your league: you enter their roster (search or paste names), both teams get their best
 * lineup under your slots and scoring, and the totals give an expected result and a win chance. Points leagues only.
 */
export default function MatchupProjector({ data, players, values, scoring, league }) {
  const [opp, setOppState] = useState(readOpponent)
  const [query, setQuery] = useState('')
  const [paste, setPaste] = useState('')
  const [unmatched, setUnmatched] = useState([])
  const [mode, setMode] = useState('daily')
  const [state, setState] = useState({ key: null, week: null, streaming: null })
  const setOpp = (next) => { setOppState(next); saveOpponent(next) }

  const mineIds = useMemo(() => new Set(players.map((p) => p.id)), [players])
  const oppIds = opp.players.map((p) => p.id)
  const isCats = league.format === 'categories'
  const key = [...players.map((p) => p.id), '|', ...oppIds].join(',')
  const anyGoalie = players.some((p) => p.kind === 'goalie') || opp.players.some((p) => p.kind === 'goalie')

  useEffect(() => {
    if (isCats || players.length === 0 || oppIds.length === 0) return
    let ignore = false
    const ids = [...new Set([...players.map((p) => p.id), ...oppIds])].join(',')
    Promise.all([
      fetch(`/api/fantasy/week?ids=${ids}&days=7`).then(ok).catch(() => null),
      anyGoalie ? fetch('/api/streaming/goalies?days=7').then(ok).catch(() => null) : null,
    ]).then(([week, streaming]) => !ignore && setState({ key, week, streaming }))
    return () => { ignore = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, isCats, anyGoalie])

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return []
    const taken = new Set(oppIds)
    const pool = [...data.skaters.map((r) => ({ ...r, kind: 'skater' })), ...data.goalies.map((r) => ({ ...r, kind: 'goalie' }))]
    return pool.filter((r) => r.name.toLowerCase().includes(q) && !taken.has(r.player_id)).slice(0, 8)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, data, key])

  const addOpp = (list) => {
    const have = new Set(oppIds)
    setOpp({ ...opp, players: [...opp.players, ...list.filter((p) => !have.has(p.id))] })
  }
  const addPasted = () => {
    const { matched, unmatched: bad } = matchNames(paste, data)
    addOpp(matched)
    setUnmatched(bad)
    setPaste(bad.join('\n'))
  }

  const ready = state.key === key
  const result = useMemo(() => {
    if (!ready || !state.week) return null
    const build = (roster) => buildEntries({ roster, week: state.week.players, streaming: state.streaming?.goalies, values, scoring, isCats })
    const mineEntries = build(players)
    const theirEntries = build(opp.players)
    const dates = [...new Set([...mineEntries, ...theirEntries].flatMap((e) => e.games.map((g) => g.date)))].sort()
    const mine = teamWeek({ entries: mineEntries, slots: league.slots, mode, scoring, dates })
    const theirs = teamWeek({ entries: theirEntries, slots: league.slots, mode, scoring, dates })
    return { mine, theirs, dates, chance: winChance(mine, theirs) }
  }, [ready, state, players, opp.players, values, scoring, isCats, league.slots, mode])

  const name = opp.name.trim() || 'Opponent'
  const chance = result ? Math.round(result.chance * 100) : null
  const clamp = (c) => (c <= 0 ? '<1%' : c >= 100 ? '>99%' : `${c}%`)

  return (
    <section>
      <h2>Matchup projector</h2>
      <p className="sub">
        Your next 7 days against another team in your league. The site can't see other teams' rosters, so enter theirs below (search, or paste
        their player names). Both teams get their best lineup under your slots and scoring (see the Lineup optimizer tab), and the gap between
        the two totals, against how much a week of scoring swings, gives a win chance. The swing is a rough estimate, not fitted to fantasy
        results, and it ignores injuries on either side, so treat the percentage as a lean, not a promise.
      </p>
      {isCats && <p className="notice">Your league counts categories, and this projector only handles points leagues (it doesn't model winning each category). Switch to a points league in Scoring &amp; backup to use it.</p>}

      {!isCats && (
        <>
          <h3>Opponent roster</h3>
          <div className="h2h-picks">
            <label className="h2h-pick">Team name (optional)
              <input type="text" value={opp.name} maxLength={40} onChange={(e) => setOpp({ ...opp, name: e.target.value })} />
            </label>
          </div>
          <div className="picker">
            <div className="search-box">
              <input type="search" placeholder="Add a player to their team…" value={query} onChange={(e) => setQuery(e.target.value)} />
              {matches.length > 0 && (
                <ul className="results">
                  {matches.map((m) => (
                    <li key={`${m.kind}${m.player_id}`}>
                      <button onClick={() => { addOpp([{ id: m.player_id, kind: m.kind, name: m.name }]); setQuery('') }}>
                        {m.name} <span>{m.team} · {m.kind === 'goalie' ? 'G' : m.position}</span>
                        {mineIds.has(m.player_id) && ' (on your team)'}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          <details className="scoring">
            <summary>Paste their roster</summary>
            <p className="muted">One name per line, or separated by commas. Numbering, teams in brackets and anything after " - " are ignored.</p>
            <textarea rows={6} style={{ width: '100%', maxWidth: 420 }} value={paste} onChange={(e) => setPaste(e.target.value)} />
            <p><button onClick={addPasted} disabled={!paste.trim()}>Add these players</button></p>
            {unmatched.length > 0 && <p className="notice">Couldn't match: {unmatched.join(', ')}. Check the spelling, or search for them above (players with no games this season aren't listed).</p>}
          </details>
          {opp.players.length > 0 && (
            <p>
              {opp.players.map((p) => (
                <span key={p.id} style={{ marginRight: 12, whiteSpace: 'nowrap' }}>
                  {p.name} <button className="link-button" onClick={() => setOpp({ ...opp, players: opp.players.filter((x) => x.id !== p.id) })}>Remove</button>
                </span>
              ))}
              <button className="link-button" onClick={() => { setOpp({ name: '', players: [] }); setUnmatched([]) }}>Clear all</button>
            </p>
          )}

          {players.length === 0 && <p className="status">Add your own players first (Roster tab).</p>}
          {players.length > 0 && opp.players.length === 0 && <p className="status">Enter the opponent's players to see the projection.</p>}
          {players.length > 0 && opp.players.length > 0 && !ready && <p className="status">Loading…</p>}
          {ready && !state.week && <p className="status">Couldn't load this week's schedule.</p>}
          {result && (
            <>
              <div className="tabs" role="group" aria-label="Lineup changes">
                <button className={mode === 'daily' ? 'on' : ''} onClick={() => setMode('daily')}>Lineups change daily</button>
                <button className={mode === 'weekly' ? 'on' : ''} onClick={() => setMode('weekly')}>Lineups lock for the week</button>
              </div>
              {result.dates.length === 0 ? <p className="status">Neither team has a game in the next 7 days.</p> : (
                <>
                  <p>
                    <strong className="accent">You {clamp(chance)}</strong> to win the week, {name} {clamp(100 - chance)}.
                    Projected {result.mine.total.toFixed(1)} to {result.theirs.total.toFixed(1)}
                    {' '}({result.mine.total >= result.theirs.total ? 'you lead by' : `${name} leads by`} {Math.abs(result.mine.total - result.theirs.total).toFixed(1)}).
                  </p>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr><th className="left">Team</th>{result.dates.map((d) => <th key={d}>{dayName(d)} {d.slice(5)}</th>)}<th>Week</th></tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td className="left">You</td>
                          {result.mine.days.map((d) => <td key={d.date}>{d.total.toFixed(1)}</td>)}
                          <td className="accent">{result.mine.total.toFixed(1)}</td>
                        </tr>
                        <tr>
                          <td className="left">{name}</td>
                          {result.theirs.days.map((d) => <td key={d.date}>{d.total.toFixed(1)}</td>)}
                          <td className="accent">{result.theirs.total.toFixed(1)}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <h3>Who drives it</h3>
                  <p>Your biggest contributors:</p>
                  <Contributors starters={result.mine.starters} />
                  <p>{name}'s:</p>
                  <Contributors starters={result.theirs.starters} />
                  <p className="muted">
                    Players with no stats yet score 0. See <Link to="?tab=lineup">the lineup optimizer</Link> for your own start/sit calls.
                  </p>
                </>
              )}
            </>
          )}
        </>
      )}
    </section>
  )
}
