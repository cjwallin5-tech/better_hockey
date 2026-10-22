import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import TeamLogo from '../components/TeamLogo.jsx'
import RestBadge from '../components/RestBadge.jsx'
import { MatchupTag, pctOff } from '../components/Matchups.jsx'
import { useUrlSync } from '../urlState.js'
import { describe } from '../glossary.js'

function useApi(url) {
  const [state, setState] = useState({ url: null, data: null, error: null })
  useEffect(() => {
    let ignore = false
    fetch(url)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`API returned ${r.status}`))))
      .then((data) => !ignore && setState({ url, data, error: null }))
      .catch((error) => !ignore && setState({ url, data: null, error: error.message }))
    return () => { ignore = true }
  }, [url])
  return state.url === url ? state : { data: null, error: null }
}

const dayName = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short' })
const n2 = (v) => (v == null ? '–' : v.toFixed(2))
const signed = (v, d = 2) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}`

function Schedule({ days, setDays, who, setWho }) {
  const { data, error } = useApi(`/api/matchups/schedule?days=${days}`)
  const key = who === 'goalies' ? 'goalies' : 'skaters'
  const ratio = who === 'goalies' ? 'goalie_ratio' : 'skater_ratio'
  const label = who === 'goalies' ? 'goalie_label' : 'skater_label'
  const rows = data ? [...data.teams].filter((t) => t[key].games > 0).sort((a, b) => b[key].index - a[key].index) : []
  return (
    <>
      <div className="h2h-picks">
        <label className="h2h-pick">Next
          <select value={days} onChange={(e) => setDays(e.target.value)}>
            {[3, 7, 10, 14].map((n) => <option key={n} value={n}>{n} days</option>)}
          </select>
        </label>
        <label className="h2h-pick">For
          <select value={who} onChange={(e) => setWho(e.target.value)}>
            <option value="skaters">Skaters (opposing defense and goalie)</option>
            <option value="goalies">Goalies (opposing offense)</option>
          </select>
        </label>
      </div>
      <p className="sub">
        Each team's games over the next {days} days, ranked by the opportunity index: the sum over its games of how much softer
        (+) or tougher (−) the opponent is than average, so it rewards both easy opponents and more games. 0.15 is worth about
        a sixth of an extra average game of chances. Differences between teams are modest, so use it to break ties.
      </p>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && rows.length === 0 && <p className="status">No games, or no ratings yet.</p>}
      {data && rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>#</th><th className="left" title={describe('Team')}>Team</th><th>Games</th><th title="Sum of (opponent ratio − 1) over the games">Opportunity index</th><th title="Average opponent ratio; above 1 is softer than average">Avg matchup</th><th className="left">Games</th></tr>
            </thead>
            <tbody>
              {rows.map((t, i) => (
                <tr key={t.team}>
                  <td>{i + 1}</td>
                  <td className="left"><TeamLogo team={t} /> <Link to={`/team/${t.team}`}>{t.team}</Link></td>
                  <td>{t[key].games}</td>
                  <td className="accent">{signed(t[key].index)}</td>
                  <td>{pctOff(t[key].avg)}</td>
                  <td className="left">
                    {t.games.map((g) => (
                      <span key={g.game_id} style={{ marginRight: 10, whiteSpace: 'nowrap' }}>
                        {dayName(g.date)} {g.home_game ? 'vs' : '@'} {g.opponent} <MatchupTag ratio={g[ratio]} label={g[label]} who={who} /><RestBadge kind={g.rest} />
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function Ratings() {
  const { data, error } = useApi('/api/matchups/teams')
  const [sort, setSort] = useState('skater_ratio')
  const rows = data ? [...data.teams].sort((a, b) => b[sort] - a[sort]) : []
  return (
    <>
      <div className="h2h-picks">
        <label className="h2h-pick">Order by
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="skater_ratio">Softest for skaters</option>
            <option value="goalie_ratio">Softest for goalies</option>
            <option value="def_ratio">Leakiest defense</option>
            <option value="off_ratio">Strongest offense</option>
          </select>
        </label>
      </div>
      <p className="sub">
        Built from expected goals (xG) on every shot, not from goals: early in a season a team's goals against says little about
        the rest of it, while its shot quality says more (tested on four past seasons). Each rating is pulled toward the league
        average by {data?.priors?.team_games ?? 20} games' worth, so it moves slowly. A goalie's effect is pulled harder still
        ({(data?.priors?.goalie_shots ?? 8000).toLocaleString()} shots' worth), because goaltending results barely repeat from year to year.
        "Offense" above 0% scores more than average; "Defense" above 0% gives up more.
      </p>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && rows.length === 0 && <p className="status">No shot data stored yet.</p>}
      {data && rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th><th className="left" title={describe('Team')}>Team</th><th>Games</th><th title={describe('xGF/G')}>xGF/G</th><th title={describe('xGA/G')}>xGA/G</th>
                <th title="Expected goals for vs the league average">Offense</th>
                <th title="Expected goals against vs the league average; above 0% is a leaky defense">Defense</th>
                <th title="Expected effect of the goalies in net, weighted by this season's starts; below 0% stops more than average">Goalie</th>
                <th title="How favorable this team is as an opponent for skaters">For skaters</th>
                <th title="How favorable this team is as an opponent for goalies">For goalies</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t, i) => (
                <tr key={t.team}>
                  <td>{i + 1}</td>
                  <td className="left"><TeamLogo team={t} /> <Link to={`/team/${t.team}`}>{t.team}</Link></td>
                  <td>{t.games}</td><td>{n2(t.xgf_pg)}</td><td>{n2(t.xga_pg)}</td>
                  <td>{pctOff(t.off_ratio)}</td><td>{pctOff(t.def_ratio)}</td><td>{pctOff(t.goalie_mult)}</td>
                  <td>{pctOff(t.skater_ratio)} <MatchupTag ratio={t.skater_ratio} label={t.skater_label} /></td>
                  <td>{pctOff(t.goalie_ratio)} <MatchupTag ratio={t.goalie_ratio} label={t.goalie_label} who="goalies" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export default function Matchups() {
  const initial = new URLSearchParams(window.location.search)
  const [tab, setTab] = useState(initial.get('tab') === 'ratings' ? 'ratings' : 'schedule')
  const [days, setDays] = useState(initial.get('days') ?? '7')
  const [who, setWho] = useState(initial.get('who') === 'goalies' ? 'goalies' : 'skaters')
  useUrlSync([['tab', tab, 'schedule'], ['days', days, '7'], ['who', who, 'skaters']])
  return (
    <main>
      <header>
        <h1>Matchups</h1>
        <p>
          Which teams have the softest and toughest schedules coming up, and how every team rates as an opponent. Good for
          deciding who to start or stream, and for breaking ties. A game on the second night of a back-to-back against a rested team is rated lower (and the rested side's higher), because teams score about a quarter of a goal fewer in those; see <Link to="/rest">back-to-backs</Link>.
        </p>
      </header>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'schedule'} className={tab === 'schedule' ? 'on' : ''} onClick={() => setTab('schedule')}>Schedule strength</button>
        <button role="tab" aria-selected={tab === 'ratings'} className={tab === 'ratings' ? 'on' : ''} onClick={() => setTab('ratings')}>Team ratings</button>
      </div>
      {tab === 'schedule' ? <Schedule days={days} setDays={setDays} who={who} setWho={setWho} /> : <Ratings />}
    </main>
  )
}
