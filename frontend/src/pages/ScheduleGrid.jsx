import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useFantasy } from '../fantasy.js'

const short = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
const dayShort = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
const NEXT = 4 // weeks in the "next few weeks" total
const level = (n) => (n <= 2 ? 'low' : n >= 4 ? 'high' : 'mid')

/** Games per team for every week of the season: light weeks, heavy weeks and back-to-backs at a glance. */
export default function ScheduleGrid() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [players, setPlayers] = useState(null)
  const [group, setGroup] = useState('all')
  const [sort, setSort] = useState('next')
  const [mine, setMine] = useState(false)
  const { list } = useFantasy()

  useEffect(() => {
    fetch('/api/schedule-grid')
      .then((r) => { if (!r.ok) throw new Error(`API returned ${r.status}`); return r.json() })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [])
  useEffect(() => {
    if (!mine || players || list.players.length === 0) return
    Promise.all([fetch('/api/skaters').then((r) => r.json()), fetch('/api/goalies').then((r) => r.json())])
      .then(([sk, gl]) => setPlayers([...sk, ...gl.goalies]))
      .catch(() => setPlayers([]))
  }, [mine, players, list.players.length])

  const rosterTeams = useMemo(() => {
    const ids = new Set(list.players.map((p) => p.id))
    return new Set((players ?? []).filter((p) => ids.has(p.player_id)).map((p) => (p.team ?? '').split(',').pop()))
  }, [players, list.players])

  const rows = useMemo(() => {
    if (!data) return []
    const nextSum = (t) => t.weeks.slice(0, NEXT).reduce((s, w) => s + w.games, 0)
    return data.teams
      .filter((t) => group === 'all' || t.division === group || t.conference === group)
      .filter((t) => !mine || rosterTeams.has(t.abbrev))
      .map((t) => ({ ...t, next: nextSum(t) }))
      .sort((a, b) => (sort === 'next' ? b.next - a.next || a.name.localeCompare(b.name) : a.name.localeCompare(b.name)))
  }, [data, group, sort, mine, rosterTeams])

  if (error) return <main><p className="status">Couldn't load the schedule: {error}</p></main>
  if (!data) return <main><p className="status">Loading…</p></main>

  return (
    <main>
      <header>
        <h1>Schedule grid</h1>
        <p>
          Games each team plays per week (Monday to Sunday). Light weeks (2 or fewer) are shaded amber and heavy weeks (4 or more)
          green. A dot marks a game on back-to-back nights. Hover a cell for the dates and opponents.
        </p>
      </header>

      <div className="controls">
        <select value={group} onChange={(e) => setGroup(e.target.value)} aria-label="Division or conference">
          <option value="all">All teams</option>
          <optgroup label="Conference">
            <option value="Eastern">Eastern</option><option value="Western">Western</option>
          </optgroup>
          <optgroup label="Division">
            {['Atlantic', 'Metropolitan', 'Central', 'Pacific'].map((d) => <option key={d}>{d}</option>)}
          </optgroup>
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort teams">
          <option value="next">Most games in the next {NEXT} weeks</option>
          <option value="name">Team name</option>
        </select>
        <label className="check">
          <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} /> Only teams on my fantasy roster
        </label>
      </div>
      {mine && list.players.length === 0 && <p className="status">Your fantasy roster is empty. <Link to="/fantasy">Add players →</Link></p>}

      <div className="table-wrap schedule-grid">
        <table>
          <thead>
            <tr>
              <th className="left">Team</th>
              <th title={`Games over the next ${NEXT} weeks`}>Next {NEXT}</th>
              {data.weeks.map((w, i) => <th key={w.start} title={`${short(w.start)} – ${short(w.end)}`}>{i === 0 ? 'This wk' : short(w.start)}</th>)}
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.abbrev}>
                <td className="left"><Link to={`/team/${t.abbrev}`}>{t.name}</Link></td>
                <td><strong>{t.next}</strong></td>
                {t.weeks.map((w, i) => (
                  <td
                    key={i}
                    className={`sg-cell ${w.games ? level(w.games) : 'none'}`}
                    title={w.days.length ? w.days.map((g) => `${dayShort(g.date)} ${g.home ? 'vs' : '@'} ${g.opp}`).join('\n') : 'No games'}
                  >
                    {w.games}{w.back_to_backs > 0 && <sup aria-label={`${w.back_to_backs} back-to-back`}>•</sup>}
                  </td>
                ))}
                <td>{t.total}</td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td className="left" colSpan={data.weeks.length + 3}>No teams match.</td></tr>}
          </tbody>
        </table>
      </div>
      <p className="sub">"This wk" counts the whole week, including games already played. A week with no games shows 0.</p>
    </main>
  )
}
