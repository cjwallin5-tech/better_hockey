import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useFantasy } from '../fantasy.js'

const mmss = (s) => `${s < 0 ? '−' : '+'}${Math.floor(Math.abs(Math.round(s)) / 60)}:${String(Math.abs(Math.round(s)) % 60).padStart(2, '0')}`
const clock = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`
const ROLE = { PP1: 'top power-play unit', PP2: 'second power-play unit', none: 'big minutes' }

/**
 * Regulars who have missed their team's latest games and what their teammates are getting. Inferred from box scores (the NHL publishes
 * no injury list), so a scratch, a trade or a call-down looks the same as an injury. See backend/absences.py and its backtest.
 */
export default function Absences() {
  const [state, setState] = useState({ data: null, error: null })
  const [team, setTeam] = useState('')
  const [mineOnly, setMineOnly] = useState(false)
  const { list } = useFantasy()
  const mine = useMemo(() => new Set(list.players.map((p) => p.id)), [list])

  useEffect(() => {
    let ignore = false
    fetch('/api/absences')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`API returned ${r.status}`))))
      .then((data) => !ignore && setState({ data, error: null }))
      .catch((error) => !ignore && setState({ data: null, error: error.message }))
    return () => { ignore = true }
  }, [])
  const { data, error } = state

  const teams = useMemo(() => [...new Set((data?.absences ?? []).map((a) => a.team))].sort(), [data])
  const shown = (data?.absences ?? []).filter((a) => (!team || a.team === team) && (!mineOnly || mine.has(a.player_id) || a.teammates.some((m) => mine.has(m.player_id))))

  return (
    <main>
      <header>
        <h1>Who&rsquo;s out, and who gets the minutes</h1>
        <p>
          Players who were regulars (in at least 7 of their team&rsquo;s last 10 games) and have missed their team&rsquo;s latest games, with what their teammates
          in the same position group are getting. The NHL publishes no injury list, so this is inferred from games missed: a scratch, a trade or a call-down
          looks the same as an injury.
        </p>
        <p className="muted">
          What four seasons of games show: only a top-role absence moves anyone&rsquo;s ice time. With a top-unit power-play forward out, the other forwards
          gain about 17 seconds a game at even strength and 10 on the power play; with a top-unit defenseman out, the other defensemen gain about 53 and 16;
          with a player who has no power-play time out, nothing measurable. The gain is spread thinly over the group, and what any one player gets is
          mostly noise (the pattern explains a few percent of a player&rsquo;s game-to-game change), so use the average as a hint, and the games already
          played without him as the better evidence.
        </p>
      </header>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && (
        <>
          <div className="controls">
            <label>Team{' '}
              <select value={team} onChange={(e) => setTeam(e.target.value)} aria-label="Team">
                <option value="">All teams</option>
                {teams.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>{' '}
            {list.players.length > 0 && (
              <label className="check"><input type="checkbox" checked={mineOnly} onChange={(e) => setMineOnly(e.target.checked)} /> Only absences that touch my roster</label>
            )}
          </div>
          {shown.length === 0 && <p className="status">No top-role regulars are out right now{team || mineOnly ? ' for this filter' : ''}.</p>}
          {shown.map((a) => (
            <section key={a.player_id}>
              <h2>
                <Link to={`/player/${a.player_id}`}>{a.name}</Link> <span className="muted">({a.team}, {a.position})</span>
                {mine.has(a.player_id) && <span className="badge warn" title="He is on your roster">yours</span>}
              </h2>
              <p className="sub">
                Out {a.games_out} game{a.games_out === 1 ? '' : 's'} since {new Date(`${a.last_played}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}.
                He averaged {clock(a.base.total)} a game ({ROLE[a.role]}{a.base.pp >= 30 ? `, ${clock(a.base.pp)} on the power play` : ''}).
              </p>
              {a.teammates.length === 0 ? <p className="status">No teammates in his position group have played since.</p> : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th className="left">Teammate</th>
                        <th title="Average ice time per game before he went out">Usual TOI</th>
                        <th title="What a teammate in this spot gains per game on average (even strength + power play), from four seasons of games">Usual gain</th>
                        <th title="Games he has played since the absence began">Games</th>
                        <th title="His ice time per game since, against his own average before (even strength + power play + shorthanded)">Gain so far</th>
                        <th title="Of which even strength / power play">EV / PP</th>
                      </tr>
                    </thead>
                    <tbody>
                      {a.teammates.map((m) => (
                        <tr key={m.player_id}>
                          <td className="left">
                            <Link to={`/player/${m.player_id}`}>{m.name}</Link>
                            {mine.has(m.player_id) && <span className="badge" title="On your roster">yours</span>}
                          </td>
                          <td>{clock(m.base_total)}</td>
                          <td className="muted">{mmss(m.expected.total)}</td>
                          <td>{m.seen.games}</td>
                          <td className="accent">{mmss(m.seen.total)}</td>
                          <td className="muted">{mmss(m.seen.ev)} / {mmss(m.seen.pp)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ))}
        </>
      )}
    </main>
  )
}
