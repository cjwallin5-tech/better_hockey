import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useUrlSync } from '../urlState.js'
import { describe } from '../glossary.js'

const n0 = (v) => Math.round(v)
const POSITIONS = [['', 'All skaters'], ['F', 'Forwards'], ['C', 'Centers'], ['L', 'Left wings'], ['R', 'Right wings'], ['D', 'Defensemen']]
const SORTS = [['final_points', 'Projected points'], ['final_goals', 'Projected goals'], ['final_assists', 'Projected assists'], ['rest_points', 'Points still to come']]

export default function Projections() {
  const initial = new URLSearchParams(window.location.search)
  const [position, setPosition] = useState(initial.get('position') ?? '')
  const [sort, setSort] = useState(initial.get('sort') ?? 'final_points')
  useUrlSync([['position', position, ''], ['sort', sort, 'final_points']])
  const [state, setState] = useState({ key: null, data: null, error: null })
  const key = `${position}|${sort}`

  useEffect(() => {
    let ignore = false
    fetch(`/api/projections?position=${position}&sort=${sort}&min_games=3&limit=100`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`API returned ${r.status}`))))
      .then((data) => !ignore && setState({ key, data, error: null }))
      .catch((error) => !ignore && setState({ key, data: null, error: error.message }))
    return () => { ignore = true }
  }, [position, sort, key])
  const { data, error } = state.key === key ? state : { data: null, error: null }

  return (
    <main>
      <header>
        <h1>Season projections</h1>
        <p>
          Where each skater's points, goals and assists are headed. Early-season rates are pulled toward the player's last
          two seasons and shot quality (expected goals) gets some credit, then applied to the games the team has left. The
          range is where the finish lands 80% of the time if no one gets hurt. In backtests over past seasons, pulling an early rate toward the player's record cut the error by about 40% against
          extrapolating the season so far (0.14 against 0.25 points a game); the expected-goals credit added about 1% on top.
        </p>
      </header>
      <div className="h2h-picks">
        <label className="h2h-pick">Position
          <select value={position} onChange={(e) => setPosition(e.target.value)}>
            {POSITIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label className="h2h-pick">Rank by
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="left">Player</th><th className="left" title={describe('Team')}>Team</th>
                <th title={describe('GP')}>GP</th><th title={describe('P')}>P</th>
                <th title="Points over a full season at the current rate">Pace</th>
                <th title="Projected points at the end of the season">Proj. P</th>
                <th title="80% range for the finish, if no one gets hurt">Range</th>
                <th title="Projected goals at the end of the season">Proj. G</th>
                <th title="Projected assists at the end of the season">Proj. A</th>
                <th title="Games the player is expected to play for the rest of the season">Games left</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.player_id}>
                  <td className="left"><Link to={`/player/${r.player_id}`}>{r.name}</Link></td>
                  <td className="left">{r.team}</td><td>{r.games_played}</td><td>{r.points}</td><td>{n0(r.point_pace)}</td>
                  <td className="accent">{n0(r.final_points)}</td><td>{n0(r.low_points)}–{n0(r.high_points)}</td>
                  <td>{n0(r.final_goals)}</td><td>{n0(r.final_assists)}</td><td>{n0(r.expected_games)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="sub">
        The range covers how lumpy scoring is and how uncertain a player's true rate is. It does not cover injuries, trades or role
        changes. For goal luck on its own, see <Link to="/luck">Luck &amp; regression</Link>.
      </p>
    </main>
  )
}
