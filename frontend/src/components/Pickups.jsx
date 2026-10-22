import { Link } from 'react-router-dom'
import { GOALIE_CATS, SKATER_CATS, fantasyPoints } from '../fantasy.js'
import { fmt1 } from '../format.js'
import { describe } from '../glossary.js'

const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))

/** Players not on your roster who are playing well right now, with fantasy points under your scoring. */
export default function Pickups({ data, kind, rosterIds, scoring, values, onAdd }) {
  const goalie = kind === 'goalie'
  const pool = (goalie ? data.goalies : data.skaters).filter((r) => !rosterIds.has(r.player_id))
  const maxGp = Math.max(0, ...pool.map((r) => r.games_played))
  const floor = Math.max(1, Math.ceil(maxGp / 3)) // skip tiny samples
  const cats = goalie ? GOALIE_CATS : SKATER_CATS
  const perGame = (r) => (r.games_played ? fantasyPoints(r, cats, scoring) / r.games_played : 0)
  const valueOf = (r) => values?.get(r.player_id)?.value
  const top = pool
    .filter((r) => r.games_played >= floor)
    .sort((a, b) => (goalie ? (b.recent_gsaa ?? -99) - (a.recent_gsaa ?? -99) : (b.recent_pace ?? -1) - (a.recent_pace ?? -1)))
    .slice(0, 10)
  if (top.length === 0) return null

  return (
    <section>
      <h2>Pickup ideas: {goalie ? 'goalies' : 'skaters'}</h2>
      <p className="sub">
        Not on your roster, ranked by recent form ({goalie ? 'goals saved above average over recent starts' : 'point pace over recent games'}),
        with at least {floor} GP. {values ? 'Value is over the rest of the season in your categories.' : 'Fantasy pts/GP uses your league scoring.'}
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left">Player</th><th className="left" title={describe('Team')}>Team</th><th title={describe('GP')}>GP</th>
              {goalie ? <><th title={describe('W')}>W</th><th title={describe('SV%')}>SV%</th><th title={describe('Recent SV%')}>Recent SV%</th><th title={describe('Recent GSAA')}>Recent GSAA</th></> : <><th title={describe('P')}>P</th><th>L{top[0]?.recent_games ?? ''} P</th><th title={describe('L10 pace')}>L10 pace</th><th title={describe('PP TOI')}>PP TOI</th></>}
              <th>{values ? 'Value' : 'Fantasy pts/GP'}</th><th />
            </tr>
          </thead>
          <tbody>
            {top.map((r) => (
              <tr key={r.player_id}>
                <td className="left">
                  <Link to={`/${goalie ? 'goalie' : 'player'}/${r.player_id}`}>{r.name}</Link>
                  {r.games_out >= 2 && <span className="badge warn" title="Not in the team's last games">out {r.games_out}</span>}
                </td>
                <td className="left">{r.team}</td><td>{r.games_played}</td>
                {goalie ? (
                  <><td>{r.wins}</td><td>{sv(r.save_pct)}</td><td>{sv(r.recent_save_pct)}</td><td className="accent">{r.recent_gsaa == null ? '–' : r.recent_gsaa.toFixed(1)}</td></>
                ) : (
                  <><td>{r.points}</td><td>{r.recent_points ?? '–'}</td><td className="accent">{fmt1(r.recent_pace)}</td>
                    <td>{r.pp_toi_per_game ? `${Math.floor(r.pp_toi_per_game / 60)}:${String(Math.round(r.pp_toi_per_game % 60)).padStart(2, '0')}` : '–'}</td></>
                )}
                <td>{values ? (valueOf(r) == null ? '–' : valueOf(r).toFixed(1)) : perGame(r).toFixed(2)}</td>
                <td><button className="link-button" onClick={() => onAdd(r)}>Add</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
