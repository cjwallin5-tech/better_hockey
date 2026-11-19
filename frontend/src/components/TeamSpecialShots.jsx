import { Link } from 'react-router-dom'
import Info from './Info.jsx'
import { fmtSv, shortDate } from '../format.js'
import { useJson } from '../lists.js'

const pct = (made, tries) => (tries ? fmtSv(made / tries) : '–')

/** A team's shootout record, shooters and goalies, and its penalty shots for and against this season (see backend/special_shots.py). */
export default function TeamSpecialShots({ abbrev }) {
  const d = useJson(`/api/teams/${abbrev}/special-shots`)
  if (!d || (d.shooters.length === 0 && d.goalies.length === 0 && d.penalty_shots.length === 0)) return null
  const shootouts = d.shootout.wins + d.shootout.losses
  return (
    <section>
      <h2>
        Shootouts &amp; penalty shots
        <Info label="Shootouts and penalty shots">
          From each game&rsquo;s play-by-play, this season only. A goalie only faces a shot that is on net, so a miss wide counts as an attempt for the
          shooter but not as a shot faced.
        </Info>
      </h2>
      {shootouts > 0 && (
        <div className="tiles tiles-compact">
          <div className="tile"><span>Shootout record</span><strong>{d.shootout.wins}-{d.shootout.losses}</strong><small>{shootouts} {shootouts === 1 ? 'shootout' : 'shootouts'}</small></div>
        </div>
      )}
      <div className="split-tables">
        {d.shooters.length > 0 && (
          <div className="table-wrap fit">
            <table>
              <thead><tr><th className="left">Shootout shooter</th><th title="Shootout attempts">Att</th><th title="Shootout goals">G</th><th title="Shootout shooting percentage">SO%</th></tr></thead>
              <tbody>
                {d.shooters.map((s) => (
                  <tr key={s.player_id}><td className="left"><Link to={`/player/${s.player_id}`}>{s.name}</Link></td><td>{s.attempts}</td><td>{s.goals}</td><td>{pct(s.goals, s.attempts)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {d.goalies.length > 0 && (
          <div className="table-wrap fit">
            <table>
              <thead><tr><th className="left">Shootout goalie</th><th title="Shootout shots faced on goal">SA</th><th title="Shootout saves">Sv</th><th title="Shootout save percentage">SV%</th></tr></thead>
              <tbody>
                {d.goalies.map((g) => (
                  <tr key={g.player_id}><td className="left"><Link to={`/goalie/${g.player_id}`}>{g.name}</Link></td><td>{g.faced}</td><td>{g.saves}</td><td>{pct(g.saves, g.faced)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {d.penalty_shots.length > 0 && (
        <div className="table-wrap fit">
          <table>
            <thead>
              <tr>
                <th className="left">Penalty shot</th><th className="left">Date</th><th className="left">Opponent</th><th className="left">Shooter</th><th className="left">Goalie</th>
                <th className="left" title="Whether it scored">Result</th>
              </tr>
            </thead>
            <tbody>
              {d.penalty_shots.map((p, i) => (
                <tr key={`${p.game_date}-${i}`}>
                  <td className="left">{p.taken ? 'Taken' : 'Faced'}</td>
                  <td className="left">{shortDate(p.game_date)}</td>
                  <td className="left"><Link to={`/team/${p.opponent}`}>{p.opponent}</Link></td>
                  <td className="left">{p.shooter ? <Link to={`/player/${p.shooter_id}`}>{p.shooter}</Link> : '–'}</td>
                  <td className="left">{p.goalie ? <Link to={`/goalie/${p.goalie_id}`}>{p.goalie}</Link> : '–'}</td>
                  <td className="left">{p.scored ? <span className="badge good">Goal</span> : <span className="muted">No goal</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
