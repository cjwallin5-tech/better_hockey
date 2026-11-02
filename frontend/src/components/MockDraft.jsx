import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { GROUPS } from '../value.js'
import { buildBoard, infoMap, needs, recommend, roundOf } from '../draft.js'
import { NOISE, myPickReview, simulate, teamTotals } from '../mockDraft.js'

const KEY = 'nhl-stats.mock-draft'
const LIMIT = 40
const GROUP_NAMES = { C: 'Center', L: 'Left wing', R: 'Right wing', D: 'Defense', G: 'Goalie' }
const BOTS = [['chalk', 'Chalk: follows the value order'], ['tight', 'Tight: a few reaches'], ['realistic', 'Realistic: some reaches and runs'], ['wild', 'Wild: anything goes']]
const BENCH = 4
const signed = (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(1)}`
const newSeed = () => Math.floor(Math.random() * 2 ** 31)

function read() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? 'null')
    const c = raw?.config
    if (!raw?.started || !c) return null
    return {
      config: { slot: Number(c.slot) || 1, snake: c.snake !== false, rounds: Number(c.rounds) || 1, noise: NOISE[c.noise] != null ? c.noise : 'realistic', seed: Number(c.seed) || 1 },
      userPicks: (Array.isArray(raw.userPicks) ? raw.userPicks : []).filter(Number.isInteger),
    }
  } catch {
    return null
  }
}

/**
 * A mock draft against bots, on the same value board as the draft helper (see mockDraft.js for how the bots pick). You draft from a slot;
 * the other teams' picks are made for you; at the end every team's best starting lineup is compared.
 * data: { skaters, goalies } season rows; values: the Map from value.js / categories.js; league: the cleaned league ({ teams, slots, format }).
 */
export default function MockDraft({ data, values, league }) {
  const board = useMemo(() => buildBoard({ values, info: infoMap(data), league }), [values, data, league])
  const unit = league.format === 'categories' ? 'z' : 'pts'
  const starters = GROUPS.reduce((t, g) => t + (league.slots[g] ?? 0), 0)
  const maxRounds = Math.max(1, Math.floor(board.length / league.teams))
  const [setup, setSetup] = useState({ slot: 1, snake: true, rounds: Math.min(maxRounds, starters + BENCH), noise: 'realistic' })
  const [run, setRun] = useState(read)   // null until started: { config, userPicks }
  const [position, setPosition] = useState('all')
  const [search, setSearch] = useState('')

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(run ? { started: true, ...run } : { started: false }))
    } catch {
      // storage unavailable: the draft just won't be remembered across a refresh
    }
  }, [run])

  const config = useMemo(
    () => (run ? { ...run.config, slot: Math.min(run.config.slot, league.teams), league: { teams: league.teams, slots: league.slots } } : null),
    [run, league],
  )
  const sim = useMemo(() => (config ? simulate({ board, config, userPicks: run.userPicks }) : null), [board, config, run])
  // a stored draft from another league size or an older board can come back with picks that no longer count: keep only the ones that did
  useEffect(() => {
    if (sim && sim.applied.length !== run.userPicks.length) setRun((r) => ({ ...r, userPicks: sim.applied }))
  }, [sim, run])

  if (board.length === 0 || board[0].value <= 0) {
    return (
      <section>
        <h2>Mock draft</h2>
        <p className="status">No player values yet. They come from the games left this season, so the mock draft opens once the new season has games played.</p>
      </section>
    )
  }

  const start = () => {
    const slot = Math.max(1, Math.min(league.teams, Math.round(Number(setup.slot)) || 1))
    const rounds = Math.max(1, Math.min(maxRounds, Math.round(Number(setup.rounds)) || 1))
    setPosition('all')
    setSearch('')
    setRun({ config: { slot, snake: setup.snake, rounds, noise: setup.noise, seed: newSeed() }, userPicks: [] })
  }

  if (!run || !sim) {
    return (
      <section>
        <h2>Mock draft</h2>
        <p className="sub">
          Draft against bots on the same player values as the draft helper ({league.teams} teams; {GROUPS.filter((g) => league.slots[g]).map((g) => `${league.slots[g]} ${g}`).join(', ')}).
          The bots take the best player by value with some mistakes, favor a position they still need, and fill their starting slots; they know
          nothing about who your league mates like, so they are plausible managers, not a prediction of yours. At the end every team's best
          starting lineup is compared.
        </p>
        <div className="h2h-picks">
          <label className="h2h-pick">Your draft slot
            <input type="number" min="1" max={league.teams} value={setup.slot} style={{ minWidth: 80, width: 80 }} onChange={(e) => setSetup({ ...setup, slot: e.target.value })} />
          </label>
          <label className="h2h-pick">Rounds
            <input type="number" min="1" max={maxRounds} value={setup.rounds} style={{ minWidth: 80, width: 80 }} onChange={(e) => setSetup({ ...setup, rounds: e.target.value })} />
          </label>
          <label className="h2h-pick">Bots
            <select value={setup.noise} onChange={(e) => setSetup({ ...setup, noise: e.target.value })}>
              {BOTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="h2h-pick" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <input type="checkbox" checked={setup.snake} onChange={(e) => setSetup({ ...setup, snake: e.target.checked })} /> Snake draft
          </label>
        </div>
        <p><button onClick={start}>Start the draft</button></p>
      </section>
    )
  }

  const { slot } = config
  const mine = sim.rosters[slot]
  const open = needs(mine.map((r) => r.group), league.slots)
  const rec = recommend(sim.available, open)
  const shown = sim.available
    .filter((r) => (position === 'all' || r.group === position) && (!search.trim() || r.name.toLowerCase().includes(search.trim().toLowerCase())))
    .slice(0, LIMIT)
  const byId = new Map(board.map((r) => [r.id, r]))
  const myPicksN = run.userPicks.length

  const draft = (id) => setRun({ ...run, userPicks: [...run.userPicks, id] })
  const undo = () => setRun({ ...run, userPicks: run.userPicks.slice(0, -1) })
  const finish = () => {
    // take the best player for a position still needed, every time it is your turn
    const picks = [...run.userPicks]
    let s = sim
    for (let guard = 0; !s.done && guard < 100; guard++) {
      const held = s.rosters[slot].map((r) => r.group)
      const pick = recommend(s.available, needs(held, league.slots)).forNeed
      if (!pick) break
      picks.push(pick.id)
      s = simulate({ board, config, userPicks: picks })
    }
    setRun({ ...run, userPicks: picks })
  }
  const restart = () => { if (!sim.done && myPicksN > 0 && !window.confirm('Throw away this draft?')) return; setRun(null) }

  const recent = sim.picks.slice(-12).reverse()
  const totals = sim.done ? teamTotals(sim.rosters, league.slots) : null
  const review = myPickReview(sim.picks, slot)

  return (
    <section>
      <h2>Mock draft</h2>
      <p>
        {sim.done ? (
          <strong>The draft is over.</strong>
        ) : (
          <>
            Pick <strong>{sim.next}</strong> (round {roundOf(sim.next, league.teams)} of {run.config.rounds}):{' '}
            <strong className="accent">you are on the clock</strong>. You are in slot {slot} of {league.teams}
            {run.config.snake ? ' in a snake draft' : ''}; bots: {BOTS.find(([v]) => v === run.config.noise)?.[1].split(':')[0].toLowerCase()}.
          </>
        )}
      </p>

      {!sim.done && (
        <>
          {rec.best && (
            <p>
              Best available: <strong>{rec.best.name}</strong> ({rec.best.position}, {signed(rec.best.value)} {unit}).
              {rec.forNeed && rec.forNeed.id !== rec.best.id && <> Best at a position you still need: <strong>{rec.forNeed.name}</strong> ({rec.forNeed.position}, {signed(rec.forNeed.value)} {unit}).</>}
              {' '}Open starting slots: {GROUPS.map((g) => `${g} ${open[g]}`).join(', ')}.
            </p>
          )}
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
                  <th title={`Value over the best free pickup at the position, in ${league.format === 'categories' ? 'z-scores' : 'fantasy points'}`}>Value</th><th />
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => (
                  <tr key={r.id}>
                    <td>{r.overall}</td>
                    <td className="left"><Link to={`/${r.kind === 'goalie' ? 'goalie' : 'player'}/${r.id}`}>{r.name}</Link></td>
                    <td>{r.group}</td><td className="left">{r.team}</td><td>{r.tier}</td>
                    <td className="accent">{signed(r.value)}</td>
                    <td><button className="link-button" onClick={() => draft(r.id)}>Draft</button></td>
                  </tr>
                ))}
                {shown.length === 0 && <tr><td colSpan={7} className="left muted">Nobody matches.</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h3>Your team ({mine.length} of {run.config.rounds})</h3>
      <ul className="roster-alerts">
        {GROUPS.map((g) => {
          const have = mine.filter((r) => r.group === g)
          return (
            <li key={g}>
              {GROUP_NAMES[g]} ({have.length}{league.slots[g] ? `, ${league.slots[g]} start` : ''}):{' '}
              {have.length ? have.map((r) => `${r.name} ${signed(r.value)}`).join(', ') : <span className="muted">none yet</span>}
            </li>
          )
        })}
      </ul>

      <p>
        {!sim.done && <><button className="link-button" onClick={finish}>Auto-draft the rest for me</button>{' '}</>}
        <button className="link-button" onClick={undo} disabled={myPicksN === 0}>Undo my last pick</button>{' '}
        <button className="link-button" onClick={restart}>{sim.done ? 'Draft again' : 'Start over'}</button>
      </p>

      {recent.length > 0 && (
        <>
          <h3>Latest picks</h3>
          <ol reversed start={recent[0].n} className="mock-feed">
            {recent.map((p) => {
              const r = byId.get(p.id)
              return (
                <li key={p.n} className={p.slot === slot ? 'accent' : undefined}>
                  Round {p.round}, team {p.slot}{p.slot === slot ? ' (you)' : ''}: {r.name} ({r.group}, {r.team}) {signed(r.value)} {unit}
                </li>
              )
            })}
          </ol>
        </>
      )}

      {totals && (
        <>
          <h2>How the draft turned out</h2>
          <p className="sub">
            Each team's best starting lineup, valued over a free pickup (a player below that counts for nothing, and an empty slot counts as a
            free pickup). You finished {totals[slot - 1].rank}{['st', 'nd', 'rd'][totals[slot - 1].rank - 1] ?? 'th'} of {league.teams}.
            Bots are not other managers: a high finish here means you drafted well against this value board, and no more.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Rank</th><th className="left">Team</th><th title="Value of the best starting lineup this team drafted">Lineup value</th><th title="Starting slots with nobody drafted for them">Empty slots</th></tr>
              </thead>
              <tbody>
                {[...totals].sort((a, b) => a.rank - b.rank).map((t) => (
                  <tr key={t.slot} className={t.slot === slot ? 'zm-row-flag' : undefined}>
                    <td>{t.rank}</td><td className="left">{t.slot === slot ? `Team ${t.slot} (you)` : `Team ${t.slot}`}</td>
                    <td className="accent">{signed(t.starters)}</td><td>{t.missing || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3>Your picks</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Pick</th><th>Round</th><th className="left">Player</th><th>Pos</th><th>Value</th><th title="How much more the best player on the board was worth when you picked">Left behind</th></tr>
              </thead>
              <tbody>
                {review.map((p) => {
                  const r = byId.get(p.id)
                  return (
                    <tr key={p.n}>
                      <td>{p.n}</td><td>{p.round}</td><td className="left">{r.name}</td><td>{r.group}</td>
                      <td className="accent">{signed(p.value)}</td><td>{p.left > 0.05 ? signed(-p.left) : ''}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="muted">Taking the best available is not always right: a position you still need can be worth more than a bigger name, so a gap in the last column is not an error.</p>
        </>
      )}
    </section>
  )
}
