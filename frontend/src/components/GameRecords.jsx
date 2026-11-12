import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Avatar from './Avatar.jsx'
import RankBadge from './RankBadge.jsx'
import { seasonLabel } from '../career.js'

const PAGE_SIZE = 50
const STAT_LABEL = { goals: 'goals', assists: 'assists', points: 'points' }

const dateLabel = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })

/**
 * The single-game records list: every game in which one skater scored at least three goals (or three assists, or three points),
 * ranked by the chosen stat, back to 1917-18. The filters live in the page above; this loads and pages its own list.
 * stat: 'goals' | 'assists' | 'points'; position: '' | 'F' | 'C' | 'L' | 'R' | 'D'.
 */
export default function GameRecords({ stat, gameType, q, position, page, setPage }) {
  const [result, setResult] = useState({ key: '', data: null, error: null })
  const params = new URLSearchParams({ stat, game_type: gameType, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
  if (q.trim()) params.set('q', q.trim())
  if (position) params.set('position', position)
  const key = params.toString()

  useEffect(() => {
    let ignore = false
    fetch(`/api/records/games?${key}`)
      .then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`)
        return r.json()
      })
      .then((data) => !ignore && setResult({ key, data, error: null }))
      .catch((error) => !ignore && setResult({ key, data: null, error: error.message }))
    return () => { ignore = true }
  }, [key])

  const { data, error } = result
  const loading = result.key !== key
  const total = data?.total ?? 0
  const lastPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1)
  const from = total ? page * PAGE_SIZE + 1 : 0
  const to = Math.min(total, (page + 1) * PAGE_SIZE)

  if (error) return <p className="status">Couldn't load the list: {error}</p>
  return (
    <>
      <p className="view-note">
        {loading ? 'Loading…' : `${from.toLocaleString()}–${to.toLocaleString()} of ${total.toLocaleString()} games with 3 or more ${STAT_LABEL[stat]}`}
      </p>
      <div className="table-wrap" style={loading ? { opacity: 0.6 } : undefined}>
        <table>
          <thead>
            <tr>
              <th className="left">Player</th>
              <th>Pos</th>
              <th>Date</th>
              <th>Season</th>
              <th>Team</th>
              <th>Opponent</th>
              <th className={stat === 'goals' ? 'sorted' : ''}>G</th>
              <th className={stat === 'assists' ? 'sorted' : ''}>A</th>
              <th className={stat === 'points' ? 'sorted' : ''}>P</th>
            </tr>
          </thead>
          <tbody>
            {(data?.rows ?? []).map((r) => (
              <tr key={`${r.player_id}-${r.game_id}`}>
                <td className="left">
                  <span className="player-cell">
                    <RankBadge n={r.place} tied={r.tied} />
                    <Avatar playerId={r.player_id} team={r.team} season={r.season_id} name={r.name} />
                    <Link to={`/player/${r.player_id}`}>{r.name}</Link>
                  </span>
                </td>
                <td>{r.position}</td>
                <td>{dateLabel(r.game_date)}</td>
                <td>{seasonLabel(r.season_id)}</td>
                <td>{r.team ?? '–'}</td>
                <td>{r.opponent ? `${r.home_road === 'R' ? '@ ' : 'vs '}${r.opponent}` : '–'}</td>
                <td className={stat === 'goals' ? 'accent sorted' : ''}>{r.goals}</td>
                <td className={stat === 'assists' ? 'accent sorted' : ''}>{r.assists}</td>
                <td className={stat === 'points' ? 'accent sorted' : ''}>{r.points}</td>
              </tr>
            ))}
            {data && data.rows.length === 0 && <tr><td className="left" colSpan={9}>No games match these filters.</td></tr>}
          </tbody>
        </table>
      </div>
      <p className="sub">
        Ties share a place: every 5-goal game ranks equally, with the earliest first. Goals and assists are credited to the player's
        team at the time. Switch to Playoffs above for postseason games.
      </p>
      <div className="pager">
        <button disabled={page === 0 || loading} onClick={() => setPage(0)}>« First</button>
        <button disabled={page === 0 || loading} onClick={() => setPage((p) => p - 1)}>‹ Prev</button>
        <span>Page {(page + 1).toLocaleString()} of {(lastPage + 1).toLocaleString()}</span>
        <button disabled={page >= lastPage || loading} onClick={() => setPage((p) => p + 1)}>Next ›</button>
        <button disabled={page >= lastPage || loading} onClick={() => setPage(lastPage)}>Last »</button>
      </div>
    </>
  )
}
