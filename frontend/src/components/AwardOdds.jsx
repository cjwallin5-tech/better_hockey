import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { describe } from '../glossary.js'

const pct = (p) => (p >= 0.995 ? '>99%' : p < 0.005 ? '<1%' : `${Math.round(p * 100)}%`)
const BASIS = {
  hart: 'Points, points per game and the team’s record, as voters have rewarded them.',
  norris: 'Points, ice time, penalty-kill time and the share of shot attempts his team gets with him on the ice. Reputation for defense is not measured.',
  calder: 'Points and points per game among rookies, and the team’s record.',
  selke: 'Points, shot-attempt share, penalty-kill time, faceoffs for centers and takeaways. Voters also weigh a defensive reputation that is not measured, so a scorer’s lead here deserves caution.',
  vezina: 'Goals saved above average, wins and the team’s record.',
}

/**
 * Win chances for the voted awards, from how voters have rewarded the stats over past seasons, applied to many plausible finishes of the
 * current season. See backend/awards.py and its backtest (backend/analysis/backtest_award_odds.py).
 */
export default function AwardOdds() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    fetch('/api/award-odds')
      .then((r) => { if (!r.ok) throw new Error(`API returned ${r.status}`); return r.json() })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <p className="status">Couldn't load award odds: {error}</p>
  if (!data) return <p className="status">Working out the odds…</p>

  return (
    <>
      <p className="sub">
        These come from a model of what voters rewarded in the seasons from 2005-06 to 2024-25 (2009-10 on for the Norris and Selke), applied to {data.draws.toLocaleString()} plausible
        finishes to this season (so a lead early on counts for much less than the same lead in April). On seasons it had not seen, it gave the
        eventual winner much more than a guess among the candidates would have. It does not know a player’s story, injuries still to come
        (a flat 12% chance of missing part of the rest of the season is assumed), or the playoffs, and it only considers skaters for the Hart and Calder.
        Goalies rarely win those.
      </p>
      {Object.entries(data.awards).map(([key, award]) => (
        <section key={key}>
          <h2>{award.trophy}</h2>
          <p className="sub">
            {BASIS[key]} Over {award.backtest.seasons} past seasons the model’s top pick won {Math.round(award.backtest.top_won * 100)}% of the time
            (it gave it {Math.round(award.backtest.top_chance * 100)}% on average), and the winner was in its top three in {award.backtest.top3} of them.
          </p>
          {award.candidates.length === 0 ? <p className="status">No candidates yet.</p> : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th className="left">Player</th><th className="left" title={describe('Team')}>Team</th><th title={describe('GP')}>GP</th>
                    <th title="Chance of winning the award">Win chance</th>
                    <th title={key === 'vezina' ? 'Wins so far' : 'Points so far'}>{key === 'vezina' ? 'W' : 'PTS'}</th>
                    {(key === 'norris' || key === 'selke') && <th title="Share of the shot attempts his team gets while he is on the ice, 5 on 5">SAT%</th>}
                    <th title={key === 'vezina' ? 'Projected wins and goals saved above average at the end of the season' : 'Projected points at the end of the season'}>Projected</th>
                  </tr>
                </thead>
                <tbody>
                  {award.candidates.map((c) => (
                    <tr key={c.player_id}>
                      <td className="left"><Link to={`/${key === 'vezina' ? 'goalie' : 'player'}/${c.player_id}`}>{c.name}</Link></td>
                      <td className="left">{c.team}</td><td>{c.games_played}</td>
                      <td className="odds-cell">
                        <div className="bar" title={`${(c.chance * 100).toFixed(1)}%`}><div style={{ width: `${c.chance * 100}%` }} /></div>
                        <strong className="accent">{pct(c.chance)}</strong>
                      </td>
                      <td>{key === 'vezina' ? c.wins : c.points}</td>
                      {(key === 'norris' || key === 'selke') && <td>{c.sat != null ? `${(c.sat * 100).toFixed(1)}%` : '–'}</td>}
                      <td className="muted">
                        {key === 'vezina' ? `${Math.round(c.final_wins)} W, ${c.final_gsaa > 0 ? '+' : ''}${c.final_gsaa.toFixed(0)} GSAA` : `${Math.round(c.final_points)} PTS`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ))}
    </>
  )
}
