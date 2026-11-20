import Info from './Info.jsx'
import { seasonLabel } from '../career.js'
import { useJson } from '../lists.js'

const dash = <span className="muted">–</span>
const ordinal = (n) => `${n}${['th', 'st', 'nd', 'rd'][(n % 100 > 10 && n % 100 < 14) || n % 10 > 3 ? 0 : n % 10]}`
const recordOf = (r) => (r ? [r.wins, r.losses, r.ties, r.overtime_losses].filter((v, i) => i < 2 || v > 0).join('-') : '–')

function Notes({ notes }) {
  return notes.length > 0 && <p className="status">{notes.join(' ')}</p>
}

/** Every captain the franchise has had, newest first, with gaps where it had none. */
function Captains({ data }) {
  if (!data.entries.length) return null
  return (
    <div>
      <h3>Captains <span className="count">{data.entries.filter((c) => !c.none).length}</span></h3>
      <div className="table-wrap fit">
        <table>
          <thead><tr><th className="left">Captain</th><th className="left" title="First and last game as captain, regular season or playoffs">Served</th></tr></thead>
          <tbody>
            {data.entries.map((c, i) => (
              <tr key={i}>
                <td className="left">{c.none ? <span className="muted">No captain</span> : c.name}</td>
                <td className="left">{c.dates ?? dash}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Notes notes={data.notes} />
    </div>
  )
}

/** The numbers the franchise has retired and who wore them. */
function RetiredNumbers({ data }) {
  if (!data.entries.length) return null
  return (
    <div>
      <h3>Retired numbers <span className="count">{data.entries.length}</span></h3>
      <div className="table-wrap fit">
        <table>
          <thead><tr><th>#</th><th className="left">Player</th><th className="left" title="Years with the franchise">Years</th></tr></thead>
          <tbody>
            {data.entries.map((r, i) => (
              <tr key={i}>
                <td><strong>{r.number}</strong></td>
                <td className="left">{r.name}{r.starred && ' *'}</td>
                <td className="left">{r.years ?? dash}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Notes notes={data.notes} />
    </div>
  )
}

/** A franchise's all-time record, Cups and playoff appearances, and a line per season (see backend/franchise.py). */
export default function TeamHistory({ abbrev }) {
  const d = useJson(`/api/teams/${abbrev}/history`)
  if (!d) return null
  return (
    <section>
      <h2>
        {d.name} history
        <Info label="Franchise history">
          From the NHL records site. A franchise keeps its record through a move or a rename, so earlier seasons may carry another team name.
          Playoff results name the last series the team played that year. Division and league finishes are blank for years before the NHL had them.
        </Info>
      </h2>
      <div className="tiles tiles-compact">
        <div className="tile"><span>Stanley Cups</span><strong>{d.cups}</strong><small>{d.final_appearances != null ? `${d.final_appearances} Finals` : ''}</small></div>
        <div className="tile"><span>Playoff appearances</span><strong>{d.playoff_appearances ?? '–'}</strong><small>in {d.seasons} seasons</small></div>
        <div className="tile wide"><span>All-time record</span><strong>{recordOf(d.regular)}</strong><small>{d.regular ? `${d.regular.points.toLocaleString()} points` : ''}</small></div>
        <div className="tile"><span>Playoff record</span><strong>{d.playoffs ? `${d.playoffs.wins}-${d.playoffs.losses}` : '–'}</strong><small>{d.playoffs ? `${d.playoffs.games_played} games` : ''}</small></div>
      </div>
      <div className="split-tables">
        <Captains data={d.captains} />
        <RetiredNumbers data={d.retired_numbers} />
      </div>
      <div className="table-wrap fit">
        <table>
          <thead>
            <tr>
              <th className="left">Season</th>
              <th title="Wins, losses and overtime losses (or ties in earlier years)">Record</th>
              <th title="Standings points">PTS</th>
              <th title="Finish in the division">Division</th>
              <th title="Finish in the whole league">League</th>
              <th className="left" title="How far the team got in the playoffs">Playoffs</th>
            </tr>
          </thead>
          <tbody>
            {d.by_season.map((s) => (
              <tr key={s.season_id}>
                <td className="left">
                  {seasonLabel(s.season_id)}
                  {s.team_name && s.team_name !== d.name && <span className="muted"> {s.team_name}</span>}
                </td>
                <td>{s.record}</td>
                <td>{s.points}</td>
                <td>{s.division_rank ? ordinal(s.division_rank) : dash}</td>
                <td>{s.league_rank ? ordinal(s.league_rank) : dash}</td>
                <td className="left">
                  {s.playoffs.champion ? <span className="badge good">Won the Stanley Cup</span>
                    : s.playoffs.text ? <span className={s.playoffs.made ? '' : 'muted'}>{s.playoffs.text}</span>
                    : <span className="muted">Season in progress</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
