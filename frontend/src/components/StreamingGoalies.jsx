import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { MatchupTag } from './Matchups.jsx'
import { streamingBoard } from '../streaming.js'
import { describe } from '../glossary.js'

const dayName = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short' })
const pct = (p) => `${Math.round(p * 100)}%`
const signed = (v, d = 1) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}`

/**
 * Goalies worth picking up for the next few days: how likely each is to start, how favorable the opponents are, and what a
 * start is expected to be worth, added up into fantasy points (points league) or a category score (category league).
 * `categories` is null for a points league. rosterIds are your players, so you can hide them.
 */
export default function StreamingGoalies({ scoring, categories, rosterIds, onAdd }) {
  const [days, setDays] = useState(5)
  const [hideMine, setHideMine] = useState(true)
  const [minStarts, setMinStarts] = useState('0.5')
  const [state, setState] = useState({ days: null, data: null, error: null })

  useEffect(() => {
    let ignore = false
    fetch(`/api/streaming/goalies?days=${days}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`API returned ${r.status}`))))
      .then((data) => !ignore && setState({ days, data, error: null }))
      .catch((error) => !ignore && setState({ days, data: null, error: error.message }))
    return () => { ignore = true }
  }, [days])

  const { data, error } = state.days === days ? state : { data: null, error: null }
  const board = useMemo(
    () => (data && data.goalies.length ? streamingBoard({ plan: data.goalies, scoring, categories, league: data.league }) : []),
    [data, scoring, categories],
  )
  const floor = Number(minStarts) || 0
  const rows = board.filter((r) => r.totals.starts >= floor && !(hideMine && rosterIds.has(r.id))).slice(0, 20)
  const mine = board.filter((r) => rosterIds.has(r.id))
  const unit = categories ? 'z' : 'pts'
  const fmtScore = (v) => (categories ? signed(v, 1) : v.toFixed(1))

  return (
    <section>
      <h2>Streaming goalies</h2>
      <p className="sub">
        Goalies to pick up for the next few days, ranked by what their starts are expected to be worth{categories ? ' across the goalie categories your league counts' : ' in fantasy points under your scoring'}.
        A goalie only scores when he starts, so each game is weighted by his chance to start it (a guess from his team's recent starts and
        back-to-backs, confirmed by the NHL close to game time). What a start is worth comes from the two teams' ratings: the
        opponent's offense, your team's defense and how likely the team is to win. A goalie's own record barely predicts
        his next season, so it counts for little here. It can't see who is available in your league, injuries, or home-ice advantage.
      </p>
      <div className="h2h-picks">
        <label className="h2h-pick">Next
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {[3, 5, 7, 10].map((n) => <option key={n} value={n}>{n} days</option>)}
          </select>
        </label>
        <label className="h2h-pick">Min expected starts
          <input type="number" min="0" max="10" step="0.5" value={minStarts} onChange={(e) => setMinStarts(e.target.value)} style={{ minWidth: 80, width: 80 }} />
        </label>
        <label className="h2h-pick" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <input type="checkbox" checked={hideMine} onChange={(e) => setHideMine(e.target.checked)} /> Hide goalies on my team
        </label>
      </div>
      {categories && categories.goalie.length === 0 && <p className="notice">No goalie categories are selected, so everyone scores 0. Pick them in the Scoring &amp; backup tab.</p>}
      {mine.length > 0 && (
        <p className="muted">
          For comparison, your goalies over the same days: {mine.map((r) => `${r.name} ${fmtScore(r.score)} ${unit} (${r.totals.starts.toFixed(1)} starts)`).join(' · ')}.
        </p>
      )}
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && board.length === 0 && <p className="status">No goalie schedule or ratings yet.</p>}
      {data && board.length > 0 && rows.length === 0 && <p className="status">Nobody meets that minimum. Try a lower number.</p>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th><th className="left">Goalie</th><th className="left" title={describe('Team')}>Team</th>
                <th title="Sum of his chances to start each game">Expected starts</th>
                <th className="left">Games (chance to start)</th>
                <th title="Expected wins over the window">Exp wins</th><th title="Expected goals against over the window">Exp GA</th>
                <th title={categories ? 'Total z-score over the goalie categories you count, against all goalies' : 'Projected fantasy points over the window'}>{categories ? 'Score (z)' : 'Projected pts'}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.id}>
                  <td>{i + 1}</td>
                  <td className="left"><Link to={`/goalie/${r.id}`}>{r.name}</Link></td>
                  <td className="left">{r.team}</td>
                  <td>{r.totals.starts.toFixed(1)}</td>
                  <td className="left">
                    {r.games.map((g) => (
                      <span key={g.game_id} style={{ marginRight: 10, whiteSpace: 'nowrap' }}>
                        {dayName(g.date)} {g.home_game ? 'vs' : '@'} {g.opponent}{g.back_to_back ? <sup title="Second game in two nights"> B2B</sup> : null}{' '}
                        <strong className={g.probability >= 0.7 || g.confirmed ? 'accent' : 'muted'}>{g.confirmed ? '✓' : pct(g.probability)}</strong>{' '}
                        <MatchupTag ratio={g.goalie_ratio} label={g.goalie_label} who="goalies" />
                      </span>
                    ))}
                  </td>
                  <td>{r.totals.win.toFixed(1)}</td><td>{r.totals.ga.toFixed(1)}</td>
                  <td className="accent">{fmtScore(r.score)}</td>
                  <td>{rosterIds.has(r.id) ? <span className="muted">on your team</span> : <button className="link-button" onClick={() => onAdd({ player_id: r.id, name: r.name }, 'goalie')}>Add</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
