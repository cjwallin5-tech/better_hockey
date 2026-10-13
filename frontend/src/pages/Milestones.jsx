import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

const day = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

export default function Milestones() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [kind, setKind] = useState('skater')
  const [stat, setStat] = useState('all')
  const [majorOnly, setMajorOnly] = useState(true)
  const [thisSeasonOnly, setThisSeasonOnly] = useState(false)

  useEffect(() => {
    fetch('/api/milestones')
      .then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`)
        return r.json()
      })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [])

  const stats = useMemo(() => {
    if (!data) return []
    const seen = new Map()
    for (const m of data.upcoming) if (m.kind === kind) seen.set(m.stat, m.label)
    return [...seen]
  }, [data, kind])

  const upcoming = useMemo(() => {
    if (!data) return []
    return data.upcoming.filter(
      (m) =>
        m.kind === kind && (stat === 'all' || m.stat === stat) && (!majorOnly || m.major) && (!thisSeasonOnly || m.this_season),
    )
  }, [data, kind, stat, majorOnly, thisSeasonOnly])

  const reached = useMemo(() => {
    if (!data) return []
    return data.reached.filter((m) => m.kind === kind && (stat === 'all' || m.stat === stat) && (!majorOnly || m.major))
  }, [data, kind, stat, majorOnly])

  if (error) return <main><p className="status">Couldn't load milestones: {error}</p></main>
  if (!data) return <main><p className="status">Loading…</p></main>

  const route = kind === 'goalie' ? 'goalie' : 'player'
  const switchKind = (k) => { setKind(k); setStat('all') }

  return (
    <main>
      <header>
        <h1>Milestone watch</h1>
        <p>
          Active players closing in on career milestones. "Games" are the player's own
          appearances at their current rate: this season's pace once they have 20 GP, otherwise
          their career average.
        </p>
      </header>

      <div className="controls">
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={kind === 'skater'} className={kind === 'skater' ? 'on' : ''} onClick={() => switchKind('skater')}>Skaters</button>
          <button role="tab" aria-selected={kind === 'goalie'} className={kind === 'goalie' ? 'on' : ''} onClick={() => switchKind('goalie')}>Goalies</button>
        </div>
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={stat === 'all'} className={stat === 'all' ? 'on' : ''} onClick={() => setStat('all')}>All</button>
          {stats.map(([id, label]) => (
            <button key={id} role="tab" aria-selected={stat === id} className={stat === id ? 'on' : ''} onClick={() => setStat(id)}>{label}</button>
          ))}
        </div>
        <label className="inline-check">
          <input type="checkbox" checked={majorOnly} onChange={(e) => setMajorOnly(e.target.checked)} /> Notable milestones only
        </label>
        <label className="inline-check">
          <input type="checkbox" checked={thisSeasonOnly} onChange={(e) => setThisSeasonOnly(e.target.checked)} /> Reachable this season
        </label>
        <span className="count">{upcoming.length} upcoming</span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left">Player</th><th className="left">Team</th><th className="left">Milestone</th>
              <th>Career now</th><th>To go</th><th>Est. games</th><th className="left">When</th>
            </tr>
          </thead>
          <tbody>
            {upcoming.slice(0, 150).map((m) => (
              <tr key={`${m.player_id}-${m.stat}`}>
                <td className="left"><Link to={`/${route}/${m.player_id}`}>{m.name}</Link></td>
                <td className="left">{m.team}</td>
                <td className="left">{m.milestone.toLocaleString()} {m.label.toLowerCase()}</td>
                <td>{m.now.toLocaleString()}</td>
                <td className="accent">{m.remaining.toLocaleString()}</td>
                <td>{m.games_needed}</td>
                <td className="left">{m.this_season ? <span className="badge">this season</span> : <span className="muted">later</span>}</td>
              </tr>
            ))}
            {upcoming.length === 0 && <tr><td className="left" colSpan="7">No milestones match these filters.</td></tr>}
          </tbody>
        </table>
      </div>
      {upcoming.length > 150 && <p className="view-note">Showing the 150 closest of {upcoming.length}. Narrow the filters to see the rest.</p>}

      <h2>Reached this season</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th className="left">Player</th><th className="left">Team</th><th className="left">Milestone</th><th className="left">Date</th><th className="left">Opponent</th></tr>
          </thead>
          <tbody>
            {reached.map((m) => (
              <tr key={`${m.player_id}-${m.stat}-${m.milestone}`}>
                <td className="left"><Link to={`/${route}/${m.player_id}`}>{m.name}</Link></td>
                <td className="left">{m.team}</td>
                <td className="left">{m.milestone.toLocaleString()} {m.label.toLowerCase()}</td>
                <td className="left">{m.date ? day(m.date) : '–'}</td>
                <td className="left">{m.opponent ? `vs ${m.opponent}` : '–'}</td>
              </tr>
            ))}
            {reached.length === 0 && <tr><td className="left" colSpan="5">None yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </main>
  )
}
