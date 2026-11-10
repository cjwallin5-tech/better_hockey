import { useEffect, useState } from 'react'
import BackLink from '../components/BackLink.jsx'
import { Link, useParams } from 'react-router-dom'
import { seasonLabel } from '../career.js'
import { CountryFlag } from '../components/Flag.jsx'
import Headshot from '../components/Headshot.jsx'
import WatchButton from '../components/WatchButton.jsx'
import { Line, draftText, height, ppg, svp } from '../components/ProspectBits.jsx'
import PageSkeleton from '../components/Skeleton.jsx'
import { nhleSentence, nhleText, nhleTitle } from '../nhle.js'
import { reachedNhl } from '../prospectStatus.js'

export default function Prospect() {
  const { id } = useParams()
  const [state, setState] = useState({ id: null, data: null, error: null })
  useEffect(() => {
    let ignore = false
    fetch(`/api/prospects/${id}`)
      .then(async (r) => (r.ok ? r.json() : Promise.reject(new Error(r.status === 404 ? 'Prospect not found' : `API returned ${r.status}`))))
      .then((data) => !ignore && setState({ id, data, error: null }))
      .catch((error) => !ignore && setState({ id, data: null, error: error.message }))
    return () => { ignore = true }
  }, [id])
  const { data: p, error } = state.id === id ? state : { data: null, error: null }
  const back = <BackLink to="/prospects" />
  if (error) return <main>{back}<p className="status">{error}</p></main>
  if (!p) return <main>{back}<PageSkeleton /></main>

  const goalie = p.position === 'G'
  return (
    <main>
      {back}
      <header>
        <div className="bio">
          <Headshot playerId={p.player_id} name={p.name} />
          <div>
            <h1><CountryFlag code={p.birth_country} /> {p.name} <span className="muted">{p.position}</span></h1>
            <p>
              {p.on_list
                ? <>Prospect of <Link to={`/team/${p.team}`}>{p.team}</Link></>
                : reachedNhl(p.seasons)
                  ? <>In the NHL now: <Link to={`/${goalie ? 'goalie' : 'player'}/${p.player_id}`}>NHL stats</Link></>
                  : <>No longer on a prospect list</>}
              {' · '}Age {p.age ?? '–'} · {height(p.height_in)}, {p.weight_lb ?? '–'} lb · Shoots {p.shoots ?? '–'} · {draftText(p.draft)}
            </p>
            <p>This season: <Line p={p} /> {p.league && <span className="muted">({p.league}, {p.club})</span>}</p>
            {p.nhle && <p className="muted" title={nhleTitle(p.nhle)}>{nhleSentence(p.nhle, p.league)}</p>}
            <p className="header-actions"><WatchButton kind="prospect" refId={p.player_id} name={p.name} /></p>
          </div>
        </div>
      </header>
      <h2>Season by season</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left">Season</th><th className="left">League</th><th className="left">Club</th><th className="left">Type</th><th>GP</th>
              {goalie ? <><th>W</th><th>SV%</th><th>GAA</th></> : <><th>G</th><th>A</th><th>P</th><th>P/GP</th><th title="NHL-equivalent points over a full season at this rate">NHLe</th><th>PIM</th><th>+/-</th></>}
            </tr>
          </thead>
          <tbody>
            {p.seasons.map((s, i) => (
              <tr key={i}>
                <td className="left">{seasonLabel(s.season_id)}</td><td className="left">{s.league}</td><td className="left">{s.team_name}</td>
                <td className="left">{s.game_type === 3 ? 'Playoffs' : 'Regular'}</td><td>{s.games}</td>
                {goalie
                  ? <><td>{s.wins ?? '–'}</td><td>{svp(s.save_pct)}</td><td>{s.gaa?.toFixed(2) ?? '–'}</td></>
                  : <><td>{s.goals ?? '–'}</td><td>{s.assists ?? '–'}</td><td>{s.points ?? '–'}</td><td className="accent">{ppg(s.points_per_game)}</td><td title={nhleTitle(s.nhle)}>{nhleText(s.nhle)}</td><td>{s.pim ?? '–'}</td><td>{s.plus_minus ?? '–'}</td></>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="sub">Every league the player has played in, from the NHL's player record. Leagues aren't comparable with one another, so judge the climb from league to league rather than the raw totals; the NHLe column translates each regular season into NHL points over a full season (see the Prospects page for how).</p>
    </main>
  )
}
